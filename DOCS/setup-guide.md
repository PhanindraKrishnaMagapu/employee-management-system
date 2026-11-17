# Setup guide

Phase 1 creates the folders and the dependency list. It does not create the database and it does not serve product screens.

You need Python 3.10 or newer and Git. Commands below use PowerShell and assume the repository is already cloned.

## 1. Go to the backend folder

```powershell
cd BACKEND
```

## 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

`venv/` is ignored by Git.

## 3. Install the Phase 1 dependencies

```powershell
pip install -r requirements.txt
```

This installs Flask, pytest, and Waitress. Waitress is reserved for deployment in a later phase.

## 4. Configure environment variables

```powershell
copy .env.example .env
```

Edit `.env` and replace `replace-with-a-long-random-string` with your own long random value. Do not commit `.env`.

Phase 1 code does not load `.env` automatically. Set the same values in the shell before you start Flask:

```powershell
$env:FLASK_SECRET_KEY = "replace-with-a-long-random-string"
$env:DATABASE_PATH = "database/ems.sqlite"
$env:FLASK_ENV = "development"
```

If `DATABASE_PATH` is relative, Flask resolves it from the `BACKEND` folder.

## 5. Start the empty application

```powershell
python run.py
```

Flask listens on `http://127.0.0.1:5000`. There is no health or employee URL yet. Opening the site root returns Flask's default "not found" page. That is expected in Phase 1.

Stop the server with Ctrl+C.

## 6. Open the frontend shell

Open `UI/index.html` in a browser. It is a static placeholder. It does not call the API yet.

The SQLite file is not created by these steps. Phase 2 will add `schema.sql` and the command that creates `database/ems.sqlite`.
