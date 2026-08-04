# Crack GRE Vocab frontend

This directory contains the clean, local-only Next.js application shell for the
private cold rebuild. It intentionally has no authentication, dashboard, study,
or backend-readiness behavior yet.

## Supported toolchain

- Node.js 24.18.x LTS (pinned in the repository `.nvmrc`)
- npm 11
- Next.js 16 and React 19
- TypeScript 7, Tailwind CSS 4, and HeroUI 3

## Local setup

From the repository root:

```bash
nvm use
cd gre-vocab-front-end
cp .env.example .env.local
npm ci
npm run dev
```

Open <http://127.0.0.1:3000>. The only application route is `/`; retired
prototype routes return the standard not-found state.

`NEXT_PUBLIC_API_BASE_URL` is a safe local placeholder reserved for AEQ-8. This
shell makes no API requests.

## Quality checks

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run start
```

The three focused tests cover the shell landmark/navigation, accessible loading
state, and generic error/retry behavior. Product feature tests belong with the
features they exercise.

## Deployment boundary

Vercel, preview deployments, CI/CD, public domains, and hosted configuration are
intentionally out of scope during Milestone 1.
