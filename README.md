# Crack GRE Vocab

Crack GRE Vocab is a focused GRE vocabulary learning application built around
active recall and adaptive review. The project is currently a private,
local-only cold rebuild: the previous prototype is retired, and Milestone 1 is
not a generally available product.

The current foundation includes a supported Django/PostgreSQL backend and a
clean Next.js application shell. Authentication, study flows, progress views,
the typed frontend/backend tracer bullet, hosted infrastructure, and deployment
automation will be added through their own scoped issues.

## Repository layout

- `crackGreVocab/` — Django REST Framework backend
- `gre-vocab-front-end/` — Next.js frontend
- `crackGreVocab/data/GRE_word.csv` — Milestone 1 vocabulary source

## Supported runtimes

- Python 3.14.6, pinned in `.python-version`
- Node.js 24.18.x LTS, pinned in `.nvmrc`
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

Open <http://127.0.0.1:3000>. The shell does not call the backend yet. See
`gre-vocab-front-end/README.md` for its supported stack, boundaries, and quality
commands.

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

The root API document should respond locally:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/
# {"service":"crack-gre-vocab-api"}
```

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
ruff check api crackGreVocab tests manage.py
mypy api crackGreVocab tests manage.py
python -m compileall -q api crackGreVocab tests manage.py
python -m pip check
python manage.py check --database default
python manage.py makemigrations --check --dry-run
python manage.py test --noinput --verbosity 2
```

## Milestone 1 boundaries

`GRE_word.csv` remains the initial vocabulary source. A dedicated import issue
will audit and normalize it, then enrich definitions and examples through free
public APIs as an offline build step. The application will use repository-owned
database content at runtime rather than depend on those APIs.

Vercel, preview deployments, CI/CD, public domains, legacy migrations, and
legacy authentication are intentionally out of scope until the rebuild is ready
to launch.
