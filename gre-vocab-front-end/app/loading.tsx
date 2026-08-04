export default function Loading() {
  return (
    <main
      aria-label="Loading application"
      aria-live="polite"
      className="mx-auto min-h-[70svh] w-full max-w-6xl px-5 py-20 sm:px-8"
      id="main-content"
      role="status"
      tabIndex={-1}
    >
      <span className="sr-only">Loading Crack GRE Vocab.</span>
      <div aria-hidden="true" className="max-w-3xl animate-pulse motion-reduce:animate-none">
        <div className="h-6 w-36 rounded-full bg-foreground/10" />
        <div className="mt-8 h-16 w-full rounded-2xl bg-foreground/10" />
        <div className="mt-4 h-16 w-4/5 rounded-2xl bg-foreground/10" />
        <div className="mt-10 h-28 w-full rounded-[1.75rem] bg-foreground/10" />
      </div>
    </main>
  );
}
