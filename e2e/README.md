# Full-stack browser verification

Playwright drives the real Next.js UI, Django API, and PostgreSQL database.
This package lives outside both applications. It uses the checked `m1-v2`
vocabulary corpus. Google OAuth is disabled; password-reset messages go to a
local file mail sink.

## Install

From the repository root, with the pinned runtimes installed:

```sh
source .venv/bin/activate
nvm use
python -m pip install -r crackGreVocab/requirements-dev.txt
npm ci --prefix gre-vocab-front-end
npm ci --prefix e2e
cd e2e
npx playwright install chromium
cd ..
```

On Linux, use `npx playwright install --with-deps chromium` from `e2e/` to
install the required browser system libraries too.

## Run

Start a local PostgreSQL server. The connection role needs permission to create
and drop databases. With the Python virtual environment active:

```sh
npm test --prefix e2e
```

The default maintenance connection is `postgresql://127.0.0.1/postgres`.
Override it explicitly when your local server needs a different user or port:

```sh
E2E_DATABASE_URL=postgresql://e2e@127.0.0.1:55432/postgres npm test --prefix e2e
```

The runner creates a randomly named `gre_e2e_*` database, applies migrations,
imports the corpus, builds the frontend, starts both servers, waits for health
responses, and runs Chromium. It stops its servers and drops only its database
on success, failure, or normal interruption. Each test uses a fresh learner and
an isolated browser context. Existing development accounts and progress remain
untouched.

Backend `.env` loading is disabled. Application connection and authentication
settings are explicitly configured for the test stack. `E2E_DATABASE_URL` is a
maintenance connection, not the application database. Only explicit localhost
PostgreSQL URLs without query parameters are accepted. A machine crash or
SIGKILL can prevent cleanup; the database name is printed at startup for manual
recovery.

| Variable | Default | Purpose |
| --- | --- | --- |
| `E2E_DATABASE_URL` | `postgresql://127.0.0.1/postgres` | Local maintenance connection |
| `E2E_API_PORT` | `8100` | Dedicated Django port |
| `E2E_WEB_PORT` | `3100` | Dedicated Next.js port |

Both servers use `127.0.0.1` with different ports, exercising browser CORS and
CSRF. Normal Django session authentication and SameSite=Lax cookies remain
enabled. HTTP uses the application's local debug configuration. Hosted HTTPS,
proxy configuration, and live Google/email delivery still need staging checks.

The frontend build uses `.next-e2e/`, separate from normal `.next/` output.
Occupied ports cause a failure rather than reuse another server. Only one E2E
run per checkout is allowed because reports and build output are shared.
The runner supports macOS and Linux.

Forward Playwright options after `--`:

```sh
npm test --prefix e2e -- --grep "study" --workers=2
npm test --prefix e2e -- --headed
npm run verify --prefix e2e
npm run report --prefix e2e
```

`verify` checks Biome, TypeScript, and browser behavior. The backend quality gate
also checks E2E Python support. Browser retries are disabled so failures remain
visible. Tests must not depend on order, shared learner accounts, or live
provider calls. Observe outcomes through the UI/API; use network interception
only for explicit failure scenarios.

## Failure evidence and CI

Playwright writes `playwright-report/` and `test-results/`, retaining traces and
screenshots for failed tests. Build/setup and server logs live under
`artifacts/gre_e2e_*/`; its `mail/` directory contains disposable reset emails.
These files contain test data and are ignored by Git. Old artifact directories
can be removed when no longer needed.

The root `.github/workflows/ci.yml` runs the backend gate, frontend gate, and this
package on pull requests, pushes to `master`, and manual dispatch. Its PostgreSQL
service is disposable and requires no repository secrets. Browser reports and
logs are uploaded for seven days, including after failures. Hosting and
deployment are separate from these checks. Configure the three job names as
required checks in GitHub branch protection when enabling the merge gate.
