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

## 🚀 Try It Out!

The web app is live! You can try it out at [www.crackgrevocab.co](http://www.crackgrevocab.co).  
- The **frontend** is hosted on Vercel.
- The **backend** is hosted on PythonAnywhere.

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

1. Install MySQL if you haven't and create a database:

   - Install MySQL Server and MySQL Workbench (optional).
   - Create a new database in MySQL for this project (e.g., `crack_gre_vocab`).

2. Set up a virtual environment:

    ```bash
    python -m venv env
    source env/bin/activate  # On Windows use \`env\Scripts\activate\`
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Configure database settings:

   - Open `settings.py` in the backend directory.
   - Update the `DATABASES` setting with your MySQL credentials:

    ```python
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'crack_gre_vocab',
            'USER': '<your_mysql_user>',
            'PASSWORD': '<your_mysql_password>',
            'HOST': 'localhost',
            'PORT': '3306',
        }
    }
    ```

5. Load initial word data:

    If there is a script to load initial data into the database, run:

    ```bash
    python manage.py import_words
    ```

6. Run database migrations:

    ```bash
    python manage.py migrate
    ```

7. Run the Django server:

    ```bash
    python manage.py runserver
    ```
