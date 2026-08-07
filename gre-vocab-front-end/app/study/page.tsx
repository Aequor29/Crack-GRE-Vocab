import type { Metadata } from "next";

import { StudySession } from "@/components/study/study-session";

export const metadata: Metadata = {
  title: "Study",
};

export default function StudyPage() {
  return (
    <main
      className="mx-auto min-h-[calc(100svh-8rem)] max-w-4xl px-5 py-12 sm:px-8 lg:py-20"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="study-title"
        className="rounded-[2rem] border border-black/10 bg-surface/90 p-7 shadow-2xl shadow-black/10 sm:p-10 dark:border-white/10 dark:shadow-black/30"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Durable recall</p>
        <h1 className="mt-3 text-4xl font-black tracking-[-0.04em] sm:text-5xl" id="study-title">
          One word at a time.
        </h1>
        <p className="mb-10 mt-4 max-w-2xl leading-7 text-foreground/65">
          Recall first, reveal the meaning, then grade yourself honestly. Your next review is
          scheduled only after the backend accepts the answer.
        </p>
        <StudySession />
      </section>
    </main>
  );
}
