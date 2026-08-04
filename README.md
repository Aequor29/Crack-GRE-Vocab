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

1. Install PostgreSQL and create a local database named `crack_gre_vocab`.

2. Set up a virtual environment and install the pinned dependencies:

    ```bash
    cd crackGreVocab
    python -m venv .venv
    source .venv/bin/activate  # On Windows use \`.venv\Scripts\activate\`
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

3. Copy the safe example configuration and replace its local placeholder values:

    ```bash
    cp .env.example .env
    ```

   Production values belong in the hosting provider's secret store. Never commit
   `.env` or working credentials.

4. Run migrations and backend checks:

    ```bash
    python manage.py migrate
    python manage.py check
    python manage.py test
    ```

5. Run the clean backend shell:

    ```bash
    python manage.py runserver
    ```

### Backend quality checks

The backend targets the Python version in `.python-version`. Install
`crackGreVocab/requirements-dev.txt`, then run:

```bash
ruff check crackGreVocab/crackGreVocab/config.py \
  crackGreVocab/crackGreVocab/settings.py
mypy crackGreVocab/crackGreVocab/config.py
cd crackGreVocab
python manage.py check
python manage.py test
```

Runtime dependencies are declared in `requirements.in` and fully pinned in
`requirements.txt`. Regenerate the lock from `crackGreVocab/` with the pinned
`uv` development tool:

```bash
uv pip compile requirements.in --output-file requirements.txt --python-version 3.14
```
