# Crack GRE Vocab frontend

This directory contains the local Next.js application for the private cold
rebuild. It includes Learner Account screens, an actionable learning-progress
dashboard, and the study-session experience. Hosted behavior remains outside
this milestone.

## Supported toolchain

- Node.js 24.20.x LTS (pinned in the repository `.nvmrc`)
- npm 11
- Next.js 16 and React 19
- TypeScript 7, Tailwind CSS 4, and HeroUI 3

## Component system

HeroUI v3 is the frontend component system for interactive controls and common
surfaces. Import components from their direct package entry points, such as
`@heroui/react/button`, so unused component families do not enter the client
bundle. Tailwind remains responsible for page layout, spacing, typography, and
product-specific visual treatment. Internal navigation continues to use
Next.js `Link` so routing stays client-side; button-like navigation uses HeroUI
variant styles rather than changing a link into a button.

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
<http://localhost:3000>. The root route sends learners to the protected
`/dashboard`; additional routes include `/sign-up`, `/sign-in`, `/account`, and
`/study`. Sign-in and sign-up offer Google OIDC when Django has fresh local
provider credentials configured. A matching password account pauses at an
explicit current-password confirmation before Google is linked.

Password recovery is available at `/forgot-password`; emailed links open
`/reset-password/confirm` with opaque identity and token parameters. Completing
a reset invalidates every existing server session and returns the learner to
`/sign-in` rather than silently authenticating the reset browser.

`NEXT_PUBLIC_API_BASE_URL` is a public, local-only origin such as
`http://localhost:8000`. The browser calls Django directly through its exact
local-origin CORS policy. Account, dashboard, and study surfaces report service
failures without exposing infrastructure details and offer recovery where the
learner can safely retry.

Use the same hostname form for both processes. `localhost:3000` pairs with
`localhost:8000`; if you choose `127.0.0.1:3000`, change the API origin to
`http://127.0.0.1:8000`. Mixing them prevents the `SameSite=Lax` Django session
cookie from accompanying API requests.

Account mutations fetch a fresh masked CSRF token and include credentials. The
frontend never stores a bearer token in local or session storage.

## Quality checks

```bash
npm run verify
```

The gate runs generated-contract drift checks, Biome, unit/component tests,
TypeScript, and the webpack production build. The complete backend gate is
`python scripts/verify_backend.py` from the repository root with its virtual
environment active. Run both gates before review; see [Testing](../TESTING.md).

The focused tests cover the application shell, dashboard progress and recovery,
typed account, progress, and study contracts, protected account behavior,
accessible form errors, study recovery, and sign out. Daily sessions rotate
through their unfinished words until each next review reaches the session's
local-day boundary. The progress bar counts completed words. Reloading restores
the current word, and completion offers a dashboard link. Product feature tests
stay with the behavior they exercise.

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
