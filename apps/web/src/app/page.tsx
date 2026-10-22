export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">RMD Knowledge Assistant</h1>
      <p className="max-w-xl text-stone-600">
        Ask questions in English, Hindi or Romanized Hindi. Answers are grounded in cited passages
        from the books and lectures.
      </p>
      <p className="devanagari text-stone-700">प्रेम रस सिद्धांत</p>
    </main>
  );
}
