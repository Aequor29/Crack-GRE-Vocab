# Product verification

## Complete local build

Install the pinned runtimes and dependencies, configure the local environments,
and initialize PostgreSQL as described in [README](README.md). From the repository
root, run:

```sh
source .venv/bin/activate
python scripts/verify_backend.py
nvm use
cd gre-vocab-front-end
npm run verify
```

The backend gate checks every maintained Python package and the verification
script. It runs Ruff, mypy, compilation, dependency consistency, Django system
checks, model/schema drift, PostgreSQL tests, and OpenAPI validation and drift.
The test runner creates and removes an isolated database through the current
forward migrations. The configured database role needs `CREATEDB` permission.
Use a local development database configuration for these commands.

The frontend gate checks generated API types, Biome, unit/component behavior,
TypeScript, and a webpack production build. Run `npm run start` to serve that
build, or `npm run dev` for interactive development. Both processes use port
3000 by default; stop one before starting the other.

GitHub Actions runs these gates and browser E2E on pull requests and pushes to
`master`. Public deployment remains paused.

## Full-stack browser verification

The root `e2e/` package drives Chromium through the real frontend and API with
an isolated PostgreSQL database. With its dependencies and Chromium installed,
run from the root with the Python virtual environment active:

```sh
npm run verify --prefix e2e
```

The runner creates a fresh database, applies migrations, imports the checked
corpus, builds and starts the applications, runs the tests, and cleans up its
database and servers. Authentication, Study, and Learning Progress are verified
through the browser, including recoverable failures. See [E2E](e2e/README.md)
for PostgreSQL configuration, focused commands, and failure artifacts.

## Test design

Name each test after the product behavior it protects. Exercise a public API,
domain operation, or user interaction and assert its returned or persisted
outcome. Add cases for distinct success, rejection, recovery, and boundary
behaviors. Keep each scenario's meaningful inputs visible.

Use small shared builders for repeated account, corpus, session, and learning
history setup. Keep mocks at external boundaries such as time, network, browser
storage, and service availability. Favor assertions about rendered state and
accepted data over private helpers, delegation calls, exact query counts,
incidental request fields, or explanatory UI copy.

Preserve coverage for account ownership, CSRF, CORS, password-recovery
non-enumeration, token expiry, session invalidation, concurrent study requests,
answer idempotency, scheduling integrity, and reproducible corpus artifacts.
Required API operations, response schemas, and CSRF headers are public
contracts. Schema assertions accept additive documented responses and fields.

Python docstrings describe the callable's role, inputs, and result where useful.
Keep implementation history and work-tracking references in review discussions.

## Focused feedback

From `crackGreVocab/`, run a behavior suite with the root environment active:

```sh
python manage.py test tests.test_study_answer_api --noinput
```

From `gre-vocab-front-end/`, run a component suite:

```sh
npm test -- test/study-flow.test.tsx
```

Run both complete gates before submitting changes for review. Corpus tests use
checked artifacts and synthetic provider responses, so they run offline.
