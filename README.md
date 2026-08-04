# 🎓 Crack-GRE-Vocab

This project is my final submission for **DIG-245 Critical Web Design** at Davidson College. The central focus of this project is to enhance the efficiency and engagement of GRE vocabulary learning through a web application.
![image](https://github.com/user-attachments/assets/8508134a-4eaa-4e17-a437-86e1cec95416)


## 📚 Project Overview

This web app designed an adaptive learning platform that uses **spaced repetition** and **active recall** techniques to maximize long-term vocabulary retention. The app offers accurate word definitions and pronunciation, allowing users to learn efficiently. Additionally, it provides a dashboard for users to view their learning progress.

### 🌟 Key Features

- **Adaptive Learning:** Utilizes spaced repetition to optimize memory retention.
- **Active Recall:** Encourages active recall practice for more effective learning.
- **Accurate Word Definitions & Pronunciation:** Helps users learn precise meanings and proper pronunciation.
- **Progress Dashboard:** Users can track their progress and stay motivated.
- **Free**

This app is perfect for college students struggling with the limited free resources available for GRE verbal preparation and aiming to improve their scores.

## 🚧 Private cold rebuild

The previous prototype is retired and the Vercel project is intentionally
paused. Milestone 1 is developed and verified locally from a clean database.
Fresh hosted infrastructure and the public launch are separate pre-GA work.

## 🛠️ Running Locally

To run the project locally, follow these steps:

### 1. Clone the Repository

```bash
git clone https://github.com/Aequor29/Crack-GRE-Vocab/
cd Crack-GRE-Vocab
```

### 2. Frontend Setup (Next.js)

Navigate to the frontend directory and install dependencies:

```bash
cd gre-vocab-front-end
npm install
npm run dev
```

### 3. Backend Setup (Django)

1. Install PostgreSQL and create a database with your local PostgreSQL role:

    ```bash
    createdb crack_gre_vocab
    ```

   The role must have `CREATEDB` permission because Django creates an isolated
   test database.

2. Set up a virtual environment and install the fully pinned development lock:

    ```bash
    cd crackGreVocab
    python -m venv .venv
    source .venv/bin/activate  # On Windows use \`.venv\Scripts\activate\`
    python -m pip install --upgrade pip
    python -m pip install --requirement requirements-dev.txt
    ```

3. Copy the safe example configuration and replace its local placeholder values:

    ```bash
    cp .env.example .env
    ```

   Production values belong in the hosting provider's secret store. Never commit
   `.env` or working credentials.

4. Build the empty database and run the backend acceptance checks:

    ```bash
    python manage.py migrate --noinput
    python manage.py migrate --check
    python manage.py makemigrations --check --dry-run
    python manage.py check --database default
    python manage.py test --noinput --verbosity 2
    ```

5. Start the backend:

    ```bash
    python manage.py runserver --noreload
    ```

6. From another shell, verify the controlled service document:

    ```bash
    curl --fail-with-body http://127.0.0.1:8000/api/
    # {"service":"crack-gre-vocab-api"}
    ```

   This static response identifies the API process. Database-aware readiness,
   OpenAPI, and the typed frontend path belong to the next tracer-bullet issue.

### Backend quality checks

The backend targets the Python version in `.python-version`. From
`crackGreVocab/`, run:

```bash
ruff check api crackGreVocab tests manage.py
mypy api crackGreVocab tests manage.py
python -m compileall -q api crackGreVocab tests manage.py
python -m pip check
python manage.py check --database default
python manage.py makemigrations --check --dry-run
python manage.py test --noinput --verbosity 2
```

Runtime and development inputs are declared separately and compiled into fully
resolved locks. Regenerate both from `crackGreVocab/` with the pinned `uv`
tool:

```bash
uv pip compile requirements.in --output-file requirements.txt --python-version 3.14
uv pip compile requirements-dev.in --output-file requirements-dev.txt --python-version 3.14
```

### Milestone 1 vocabulary seed

`crackGreVocab/data/GRE_word.csv` remains the initial vocabulary source.
AEQ-12 will audit and normalize it, then enrich definitions and examples through
free public APIs as an offline build step. Production will read the resulting
repository-owned database content and will not depend on those APIs at runtime.
