# Setup Guide – Employee Management System

**Current Status:** Phase 2 – Database Foundation Implemented

This guide explains how to set up the Employee Management System on Windows using PowerShell.

## Requirements

- Python 3.10 or newer
- Git
- PowerShell
- Visual Studio Code or another code editor

## 1. Clone the Repository

```powershell
git clone https://github.com/PhanindraKrishnaMagapu/employee-management-system.git
cd employee-management-system
```

## 2. Create a Virtual Environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again.

## 3. Install Backend Dependencies

```powershell
cd BACKEND
python -m pip install -r requirements.txt
```

Installed packages include:

- Flask – Backend framework
- pytest – Automated testing
- Waitress – Production WSGI server for a later deployment phase

## 4. Configure Environment Variables

Copy the example file:

```powershell
copy .env.example .env
```

Edit `.env` and replace the secret-key placeholder with a long random value.

Example configuration:

```dotenv
FLASK_SECRET_KEY=replace-with-a-long-random-string
DATABASE_PATH=database/ems.sqlite
FLASK_ENV=development
```

Do not commit `.env` to Git.

The application currently reads environment variables from the shell. It does not automatically load `.env`.

PowerShell configuration example:

```powershell
$env:FLASK_SECRET_KEY = "replace-with-a-long-random-string"
$env:DATABASE_PATH = "database/ems.sqlite"
$env:FLASK_ENV = "development"
```

Relative database paths are resolved from the `BACKEND` directory.

## 5. Initialize the SQLite Database

From the `BACKEND` directory, run:

```powershell
python -m app.db init
```

This command:

- Creates the SQLite database if it does not exist.
- Creates all 15 application tables.
- Enables foreign-key enforcement through database connections.
- Inserts fictional development seed data.

The database is stored at:

```text
BACKEND/database/ems.sqlite
```

To create tables without inserting demo data:

```powershell
python -m app.db init --no-seed
```

## 6. Run Automated Database Tests

From the `BACKEND` directory:

```powershell
python -m pytest tests/test_schema.py -v
```

The current Phase 2 test suite checks:

1. All 15 tables are created.
2. Foreign keys are enabled.
3. Demo employees and users are inserted.
4. Duplicate employee codes are rejected.
5. Salary records require an existing employee.
6. Repeated initialization does not duplicate demo records.

Latest verified result: **6 passed, 0 failed.**

Tests use temporary databases and do not modify the local development database.

## 7. Start the Flask Application

From the `BACKEND` directory:

```powershell
python run.py
```

The development server is expected to listen on:

```text
http://127.0.0.1:5000
```

Stop the server using `Ctrl + C`.

Employee and authentication API endpoints will be implemented in later phases.

## 8. Frontend

The frontend is located in:

```text
UI/
```

Open `UI/index.html` in a browser to view the current static frontend shell.

Frontend API integration will be implemented in later phases.

## 9. Important Git and Security Notes

The following files and folders must not be committed:

- `.venv/`
- `BACKEND/.env`
- `BACKEND/database/ems.sqlite`

Only fictional development records should be used.

Never commit real employee personal information, salary data, passwords, or secret keys.

## 10. Project Documentation

Refer to:

- `MASTER_SOW.md` – Project requirements and scope.
- `DOCS/architecture.md` – System architecture.
- `DOCS/database-design.md` – Database tables and relationships.
- `DOCS/api-documentation.md` – API documentation.
- `DOCS/user-guide.md` – Application usage guide.
