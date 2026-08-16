# Crack GRE Vocab

Crack GRE Vocab is a focused GRE vocabulary learning application built around
active recall and adaptive review. The project is currently a private,
local-only cold rebuild: the previous prototype is retired, and Milestone 1 is
not a generally available product.

The current foundation includes a supported Django/PostgreSQL backend, a clean
Next.js application shell, a generated typed API boundary, and Learner Accounts
backed by Django sessions. Study flows, progress views, hosted infrastructure,
and deployment automation remain separately scoped work.

## Repository layout

- `crackGreVocab/` — Django REST Framework backend
- `gre-vocab-front-end/` — Next.js frontend
- `crackGreVocab/data/GRE_word.csv` — Milestone 1 vocabulary source
- `crackGreVocab/vocabulary/README.md` — corpus rebuild and import runbook

## Supported runtimes

- Python 3.14.6, pinned in `.python-version`
- Node.js 24.19.x LTS, pinned in `.nvmrc`
- npm 11
- PostgreSQL for the Django database

## Frontend setup

From the repository root:

```bash
nvm use
cd gre-vocab-front-end
cp .env.example .env.local
npm ci
npm run dev
```

Open <http://localhost:3000>. The readiness card and account screens call the local Django service
configured by `NEXT_PUBLIC_API_BASE_URL`; it remains usable and offers a manual
retry when Django or PostgreSQL is unavailable. See `gre-vocab-front-end/README.md`
for its supported stack, boundaries, and quality commands.

Keep the frontend and API hostnames paired: use `localhost:3000` with
`localhost:8000`, or `127.0.0.1:3000` with `127.0.0.1:8000`. Although both
origins are allowed locally, mixing the hostname forms makes them different
sites and prevents the `SameSite=Lax` session cookie from being sent.

## Backend setup

Create an empty local PostgreSQL database, then install the pinned development
dependencies:

```bash
createdb crack_gre_vocab
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --requirement crackGreVocab/requirements-dev.txt
cp crackGreVocab/.env.example crackGreVocab/.env
```

Replace the safe placeholders in `crackGreVocab/.env`, then initialize and run
the service:

```bash
cd crackGreVocab
python manage.py migrate --noinput
python manage.py check --database default
python manage.py test --noinput --verbosity 2
python manage.py runserver --noreload
```

The process document and database-aware readiness endpoint should respond
locally:

```bash
curl --fail-with-body http://localhost:8000/api/
# {"service":"crack-gre-vocab-api"}

curl --fail-with-body http://localhost:8000/api/readiness/
# {"status":"ready","database":"available"}
```

`/api/` is intentionally database-independent. `/api/readiness/` returns HTTP
503 with a generic unavailable document when PostgreSQL cannot answer, without
exposing connection details. The raw OpenAPI document is available at
`/api/schema/`.

## Learner account contract

Create an account at <http://localhost:3000/sign-up>, sign in at
<http://localhost:3000/sign-in>, and inspect or end the current session at
<http://localhost:3000/account>. Django stores password hashes and session
state; the browser stores no bearer credential. Every unsafe request first
obtains a masked CSRF token and sends it with the credentialed request.

For the private Milestone 1 UX, signup reports that an email already exists so
a learner can correct an accidental repeat signup. This deliberately reveals
account existence. Request throttling and reconsideration of that disclosure
belong to pre-GA security hardening, before the app is publicly reachable.

`LearnerAccount` is the first clean account schema. If an older local foundation
database was migrated before this model existed, recreate the empty local
database; no prototype user or authentication migration is supported.

## Password recovery contract

Request recovery at <http://localhost:3000/forgot-password>. The API always
returns the same accepted response for a valid email-shaped request, whether or
not a recoverable account exists. Development sends reset messages to Django's
console mail sink; configure `PASSWORD_RESET_FRONTEND_URL` with the same local
hostname form used by the frontend.

Reset tokens expire after 30 minutes and become invalid after one successful
password change. A rejected replacement password does not consume the token.
Changing the password changes Django's authentication hash, so every existing
session for that learner—including a session in the browser completing the
reset—is rejected on its next authenticated request. Recovery never preserves
or silently refreshes an existing session. A fresh transactional mail backend,
sender, and hosted reset URL are required when non-debug hosting is enabled.

## Google sign-in contract

Google sign-in uses the authorization-code OpenID Connect flow through Django.
The backend validates provider state, nonce, signature, issuer, audience, and
token expiry through Authlib, then uses Google's stable `sub` claim as the
external identity key. Provider access and refresh tokens are not persisted.

A verified Google identity with a new email creates a learner with an unusable
local password. A returning `sub` signs into its existing learner even if the
provider email later changes. A verified email that matches an existing
password account never merges silently: the callback creates a ten-minute
pending link and requires the learner's current password before attaching the
Google identity. A different Google subject already associated with that email
is an explicit conflict.

Google sign-in stays disabled when both credential settings are empty. For
local testing, create fresh Web OAuth credentials and configure the exact
callback shown in `crackGreVocab/.env.example`; never reuse prototype OAuth
credentials. Non-debug hosting requires explicit hosted callback and frontend
URLs.

## Quality checks

Run frontend checks from `gre-vocab-front-end/`:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Run backend checks from `crackGreVocab/` with the virtual environment active:

```bash
ruff check accounts api crackGreVocab tests manage.py
mypy accounts api crackGreVocab tests manage.py
python -m compileall -q accounts api crackGreVocab tests manage.py
python -m pip check
python manage.py check --database default
python manage.py makemigrations --check --dry-run
python manage.py test --noinput --verbosity 2
```

Regenerate and validate the typed API boundary after changing an endpoint:

```bash
cd crackGreVocab
python manage.py spectacular --file openapi.json --format openapi-json --validate --fail-on-warn
cd ../gre-vocab-front-end
npm run api:generate
npm run typecheck
cd ..
git diff --exit-code -- crackGreVocab/openapi.json gre-vocab-front-end/lib/api/generated
```

On a clean checkout, that final command fails when the committed schema or
generated TypeScript types have drifted. `npm run api:check` is the shorthand
frontend drift gate after `openapi.json` has been regenerated. Review and commit
both artifacts when an API change is intentional.

## Local full-stack smoke

With PostgreSQL, Django, and Next.js running as described above, open
<http://localhost:3000> and confirm the readiness card announces `Backend and
database ready`. Stop PostgreSQL and choose `Try again` to confirm the generic
database-unavailable state, then restart PostgreSQL and retry to confirm
recovery. This exercises the browser, exact local-origin CORS policy, Django,
and PostgreSQL without introducing hosted infrastructure.

For the account smoke, create a learner, reload `/account` to confirm session
restoration, sign out and confirm the protected page returns to sign in, then
sign in again with the same normalized email identity.

## Milestone 1 boundaries

`GRE_word.csv` remains the initial vocabulary source. The dedicated vocabulary
app now audits and normalizes it, pins Open English WordNet 2025 by URL and
SHA-256, produces an explicit human-review/fallback queue, builds immutable
artifacts without network access, and imports them atomically into versioned
PostgreSQL tables. See the
[vocabulary corpus runbook](crackGreVocab/vocabulary/README.md) for all six
commands, review decisions and overrides, provider pacing, offline build,
activation, and idempotent import behavior.

The reviewed `m1-v1` release is checked in with 3,034 canonical words and 3,389
paired definition/example senses. Its review queue is empty: 22 words use the
narrow automatic policy, 2,399 use explicit provider-sense decisions, and 613
use explicit editorial overrides. Builds and imports fail closed on changed or
invalid input, and the application never depends on dictionary APIs at runtime.

Email verification delivery, Vercel, preview deployments, CI/CD, public domains,
legacy migrations, and legacy authentication are intentionally out of scope
until their dedicated milestones.
