# Crack GRE Vocab frontend

This directory contains the clean, local-only Next.js application shell for the
private cold rebuild. It intentionally has no authentication, dashboard, study,
or hosted behavior. Its first real integration is a typed readiness request to
the local Django/PostgreSQL backend.

## Supported toolchain

- Node.js 24.19.x LTS (pinned in the repository `.nvmrc`)
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

Start Django as described in the repository README, then open
<http://127.0.0.1:3000>. The only application route is `/`; retired prototype
routes return the standard not-found state.

`NEXT_PUBLIC_API_BASE_URL` is a public, local-only origin such as
`http://127.0.0.1:8000`. The browser calls Django directly through its exact
local-origin CORS policy. The page reports ready, database unavailable, or
backend unavailable without displaying exception or connection details, and
expected outages can be retried manually.

## Quality checks

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run start
```

The focused tests cover the existing shell states plus ready, database-down,
backend-down, malformed-response, and interactive recovery behavior. Product
feature tests belong with the features they exercise.

## Typed API contract

The committed `lib/api/generated/schema.generated.ts` file is generated from
`../crackGreVocab/openapi.json`; it is not handwritten. After an intentional
backend contract change, regenerate and validate the OpenAPI document first,
then update the frontend model with:

```bash
npm run api:generate
```

From a clean checkout, verify that the committed frontend model has not drifted
with:

```bash
npm run api:check
```

This regenerates the TypeScript model and fails if the committed output changes.
The generator is a pinned development dependency and does not add a browser
runtime client.

## Deployment boundary

Vercel, preview deployments, CI/CD, public domains, and hosted configuration are
intentionally out of scope during Milestone 1.
