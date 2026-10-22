"use client";

export const TOKEN_KEY = "rmd_admin_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string | null) {
  if (t) window.sessionStorage.setItem(TOKEN_KEY, t);
  else window.sessionStorage.removeItem(TOKEN_KEY);
}
