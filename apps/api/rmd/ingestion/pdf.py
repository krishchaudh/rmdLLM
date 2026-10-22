"""PDF ingestion: page rendering, text-layer detection, OCR (tesseract and/or vision LLM), page metadata.

Every page record keeps: 0-based `page_index`, detected `printed_page_number`, `extraction_method`
(text | ocr_vision | ocr_tesseract | empty), a confidence in [0,1], page size and a review flag.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pymupdf as fitz

from rmd.providers.base import Usage

MIN_TEXT_CHARS_FOR_TEXT_LAYER = 40
RENDER_DPI = 300
VISION_MAX_HEIGHT = 1600

PRINTED_PAGE_RE = re.compile(r"^\W*(\d{1,4}|[ivxlc]{1,7})\W*$", re.IGNORECASE)


@dataclass
class PageResult:
    page_index: int
    text: str
    extraction_method: str
    confidence: float | None
    width: float
    height: float
    printed_page_number: str | None = None
    needs_review: bool = False
    review_reason: str | None = None
    word_boxes: list[dict] | None = None
    usage: Usage = field(default_factory=Usage)
    tesseract_text: str | None = None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def open_pdf(path: str) -> fitz.Document:
    doc = fitz.open(path)
    if doc.is_encrypted:
        raise ValueError("encrypted PDFs are not supported")
    return doc


def page_text_layer(page: fitz.Page) -> str:
    return page.get_text("text").strip()


def render_page_gray(page: fitz.Page, dpi: int = RENDER_DPI) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def deskew(img: np.ndarray) -> np.ndarray:
    thr = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if len(coords) < 100:
        return img
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.2 or abs(angle) > 15:
        return img
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def binarize(img: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15
    )


def encode_png_for_vision(img: np.ndarray, max_height: int = VISION_MAX_HEIGHT) -> bytes:
    h, w = img.shape[:2]
    if h > max_height:
        scale = max_height / h
        img = cv2.resize(img, (int(w * scale), max_height), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("png encode failed")
    return buf.tobytes()


def tesseract_ocr(img: np.ndarray, lang: str = "eng") -> tuple[str, float | None, list[dict]]:
    """Returns (text, mean_word_confidence 0..1, word boxes). Requires the tesseract binary."""
    import pytesseract

    prepared = binarize(deskew(img))
    data = pytesseract.image_to_data(
        prepared, lang=lang, config="--psm 4", output_type=pytesseract.Output.DICT
    )
    words: list[dict] = []
    confs: list[float] = []
    for i, txt in enumerate(data["text"]):
        if not txt.strip():
            continue
        c = float(data["conf"][i])
        if c < 0:
            continue
        confs.append(c)
        words.append(
            {
                "t": txt,
                "x": int(data["left"][i]),
                "y": int(data["top"][i]),
                "w": int(data["width"][i]),
                "h": int(data["height"][i]),
                "c": round(c),
                "ln": int(data["line_num"][i]),
                "blk": int(data["block_num"][i]),
            }
        )
    text = pytesseract.image_to_string(prepared, lang=lang, config="--psm 4").strip()
    conf = (sum(confs) / len(confs) / 100.0) if confs else None
    return text, conf, words


def _norm_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def agreement_score(a: str, b: str) -> float:
    """Token-set F1 between two transcriptions (ASCII-folded). 1.0 = identical word sets."""
    ta, tb = set(_norm_tokens(_ascii_fold(a))), set(_norm_tokens(_ascii_fold(b)))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if inter == 0:
        return 0.0
    p, r = inter / len(tb), inter / len(ta)
    return 2 * p * r / (p + r)


def _ascii_fold(s: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def detect_printed_page_number(text: str) -> str | None:
    """Look at the first/last short lines for a bare page number (decimal or roman)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    candidates = lines[:1] + lines[-2:]
    for ln in reversed(candidates):
        cleaned = re.sub(r"[^\w]", " ", ln).strip()
        m = PRINTED_PAGE_RE.match(cleaned)
        if m and len(cleaned) <= 8:
            return m.group(1).lower()
    return None


def _is_blank(text: str) -> bool:
    t = text.strip().lower()
    return not t or t in ("[blank page]", "[illegible]")


def extract_page(
    page: fitz.Page,
    page_index: int,
    *,
    llm=None,
    use_vision: bool = True,
    use_tesseract: bool = True,
    tesseract_lang: str = "eng",
    agreement_review_threshold: float = 0.6,
) -> PageResult:
    rect = page.rect
    text_layer = page_text_layer(page)
    if len(text_layer) >= MIN_TEXT_CHARS_FOR_TEXT_LAYER:
        return PageResult(
            page_index,
            text_layer,
            "text",
            1.0,
            rect.width,
            rect.height,
            printed_page_number=detect_printed_page_number(text_layer),
        )

    img = render_page_gray(page)
    if img.std() < 3.0:  # uniformly blank raster
        return PageResult(page_index, "", "empty", None, rect.width, rect.height)

    tess_text, tess_conf, boxes = (None, None, None)
    if use_tesseract:
        try:
            tess_text, tess_conf, boxes = tesseract_ocr(img, tesseract_lang)
        except Exception:  # noqa: BLE001 - tesseract missing or crashed; vision can still proceed
            tess_text, tess_conf, boxes = None, None, None

    if use_vision and llm is not None:
        result = llm.ocr_image(encode_png_for_vision(img))
        vision_text = result.text.strip()
        if _is_blank(vision_text):
            return PageResult(
                page_index,
                "",
                "empty",
                None,
                rect.width,
                rect.height,
                usage=result.usage,
                tesseract_text=tess_text,
            )
        agreement = agreement_score(vision_text, tess_text) if tess_text else None
        confidence = agreement if agreement is not None else None
        needs_review = (agreement is not None and agreement < agreement_review_threshold) or (
            "[illegible]" in vision_text
        )
        reason = None
        if needs_review:
            reason = (
                f"low OCR agreement {agreement:.2f}"
                if agreement is not None and agreement < agreement_review_threshold
                else "illegible region"
            )
        return PageResult(
            page_index,
            vision_text,
            "ocr_vision",
            confidence,
            rect.width,
            rect.height,
            printed_page_number=detect_printed_page_number(vision_text),
            needs_review=needs_review,
            review_reason=reason,
            word_boxes=boxes,
            usage=result.usage,
            tesseract_text=tess_text,
        )

    if tess_text is not None:
        needs_review = tess_conf is None or tess_conf < 0.6
        return PageResult(
            page_index,
            tess_text,
            "ocr_tesseract",
            tess_conf,
            rect.width,
            rect.height,
            printed_page_number=detect_printed_page_number(tess_text),
            needs_review=needs_review,
            review_reason="low tesseract confidence" if needs_review else None,
            word_boxes=boxes,
        )
    return PageResult(
        page_index,
        "",
        "empty",
        None,
        rect.width,
        rect.height,
        needs_review=True,
        review_reason="no OCR engine produced text",
    )
