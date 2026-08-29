"use client";

import { Button } from "@heroui/react/button";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ reset }: ErrorPageProps) {
  return (
    <main
      className="mx-auto grid min-h-[70svh] max-w-3xl place-items-center px-5 py-20 text-center sm:px-8"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="error-title"
        className="rounded-[2rem] border border-danger/25 bg-surface p-8 sm:p-12"
        role="alert"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-danger">Page unavailable</p>
        <h1 className="mt-4 text-4xl font-black tracking-[-0.04em]" id="error-title">
          We couldn&apos;t load this page.
        </h1>
        <p className="mx-auto mt-4 max-w-xl leading-7 text-foreground/65">
          Nothing sensitive is shown here. Try the request again, or return home if the problem
          continues.
        </p>
        <div className="mt-8">
          <Button onPress={reset} variant="primary">
            Try again
          </Button>
        </div>
      </section>
    </main>
  );
}
