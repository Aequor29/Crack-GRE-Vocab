import type { Metadata } from "next";

import { StudySession } from "@/components/study/study-session";

export const metadata: Metadata = {
  title: "Study",
};

export default function StudyPage() {
  return (
    <main
      className="mx-auto min-h-[calc(100svh-8rem)] max-w-4xl px-5 py-8 sm:px-8 lg:py-12"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="study-title"
        className="rounded-[2rem] border border-black/10 bg-surface/90 p-7 shadow-2xl shadow-black/10 sm:p-10 dark:border-white/10 dark:shadow-black/30"
      >
        <h1 className="sr-only" id="study-title">
          Study vocabulary
        </h1>
        <StudySession />
      </section>
    </main>
  );
}
