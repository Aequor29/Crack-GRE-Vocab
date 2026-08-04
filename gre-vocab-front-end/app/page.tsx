import { ReadinessStatus } from "@/components/readiness-status";

const principles = [
  {
    number: "01",
    title: "One focused study loop",
    description: "Recall, reveal, and self-grade without managing a spaced-repetition system.",
  },
  {
    number: "02",
    title: "Adaptive under the hood",
    description:
      "The backend will decide what is useful to review while the interface stays simple.",
  },
  {
    number: "03",
    title: "Progress without hype",
    description:
      "Useful trends will explain current learning state without promising permanent mastery.",
  },
] as const;

const foundationStatus = [
  { label: "Django + PostgreSQL foundation", state: "Ready" },
  { label: "Accessible frontend shell", state: "Ready" },
] as const;

export default function HomePage() {
  return (
    <main id="main-content" tabIndex={-1}>
      <section className="relative isolate overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-[-24rem] -z-10 mx-auto h-[46rem] max-w-5xl rounded-full bg-[radial-gradient(circle,rgba(111,91,255,0.22),transparent_68%)] blur-3xl dark:bg-[radial-gradient(circle,rgba(139,124,255,0.18),transparent_68%)]"
        />
        <div className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-6xl items-center gap-14 px-5 py-20 sm:px-8 lg:grid-cols-[1.15fr_0.85fr] lg:py-24">
          <div className="max-w-3xl">
            <p className="mb-7 inline-flex rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-accent">
              Milestone 1 · Local only
            </p>
            <h1 className="max-w-4xl text-balance text-[clamp(3.25rem,8vw,6.75rem)] font-black leading-[0.92] tracking-[-0.065em]">
              Build recall that lasts.
            </h1>
            <p className="mt-8 max-w-2xl text-pretty text-lg leading-8 text-foreground/70 sm:text-xl">
              Crack GRE Vocab is being rebuilt as a focused study experience that plans useful
              reviews while learners stay focused on the words.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <a
                className="rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-foreground shadow-xl shadow-accent/20 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background motion-reduce:transform-none"
                href="#status"
              >
                View rebuild status
              </a>
              <span className="text-sm text-foreground/65">No account or deployment required</span>
            </div>
          </div>

          <aside
            aria-labelledby="foundation-card-title"
            className="relative overflow-hidden rounded-[2rem] border border-black/10 bg-surface/80 p-6 shadow-2xl shadow-black/10 backdrop-blur sm:p-8 dark:border-white/10 dark:shadow-black/30"
          >
            <div
              aria-hidden="true"
              className="absolute -right-16 -top-20 size-48 rounded-full bg-accent/15 blur-3xl"
            />
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-foreground/65">
              Clean foundation
            </p>
            <h2 className="mt-3 text-2xl font-bold tracking-tight" id="foundation-card-title">
              Small, supported, dependable.
            </h2>
            <dl className="mt-8 space-y-1">
              {foundationStatus.map((item) => (
                <div
                  className="flex items-center justify-between gap-6 border-t border-black/10 py-4 first:border-t-0 dark:border-white/10"
                  key={item.label}
                >
                  <dt className="text-sm text-foreground/70">{item.label}</dt>
                  <dd className="rounded-full bg-background px-3 py-1 text-xs font-bold text-foreground">
                    {item.state}
                  </dd>
                </div>
              ))}
              <ReadinessStatus />
              <div className="flex items-center justify-between gap-6 border-t border-black/10 py-4 dark:border-white/10">
                <dt className="text-sm text-foreground/70">Learner features</dt>
                <dd className="rounded-full bg-background px-3 py-1 text-xs font-bold text-foreground">
                  Planned
                </dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>

      <section className="scroll-mt-24 border-y border-black/10 dark:border-white/10" id="status">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 sm:px-8 lg:grid-cols-[0.75fr_1.25fr] lg:py-28">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">
              Rebuild status
            </p>
            <h2 className="mt-4 text-4xl font-black tracking-[-0.04em] sm:text-5xl">
              The shell is ready for real product work.
            </h2>
          </div>
          <div className="grid gap-5 text-base leading-7 text-foreground/70 sm:grid-cols-2">
            <p>
              This frontend intentionally contains no inherited dashboard, authentication, or study
              behavior. The first local contract now reports whether Django and PostgreSQL are
              ready.
            </p>
            <p>
              The typed boundary is generated from Django&apos;s OpenAPI document and keeps expected
              downtime visible and retryable—still entirely in local development.
            </p>
          </div>
        </div>
      </section>

      <section
        className="scroll-mt-24 mx-auto max-w-6xl px-5 py-20 sm:px-8 lg:py-28"
        id="principles"
      >
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">
            Product principles
          </p>
          <h2 className="mt-4 text-4xl font-black tracking-[-0.04em] sm:text-5xl">
            Simple outside. Thoughtful inside.
          </h2>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {principles.map((principle) => (
            <article
              className="rounded-[1.75rem] border border-black/10 bg-surface p-7 dark:border-white/10"
              key={principle.number}
            >
              <p className="text-sm font-black text-accent">{principle.number}</p>
              <h3 className="mt-8 text-xl font-bold tracking-tight">{principle.title}</h3>
              <p className="mt-3 leading-7 text-foreground/65">{principle.description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
