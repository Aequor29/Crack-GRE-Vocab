import Link from "next/link";

export default function NotFound() {
  return (
    <main
      className="mx-auto grid min-h-[70svh] max-w-3xl place-items-center px-5 py-20 text-center sm:px-8"
      id="main-content"
      tabIndex={-1}
    >
      <section aria-labelledby="not-found-title">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">404 · Not found</p>
        <h1 className="mt-4 text-4xl font-black tracking-[-0.04em]" id="not-found-title">
          This route isn&apos;t part of the rebuild.
        </h1>
        <p className="mt-4 leading-7 text-foreground/65">
          The prototype routes were intentionally retired so new features can start from clear
          contracts.
        </p>
        <Link
          className="mt-8 inline-flex rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background"
          href="/"
        >
          Return home
        </Link>
      </section>
    </main>
  );
}
