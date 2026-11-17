# Employee Management System - Backend

## Overview
This folder contains the backend application.

## Technology Stack
- Python
- Flask
- REST API

## Backend Responsibilities
- Add employee
- View employee details
- Update employee details
- Delete employee
- Connect with database

## API Modules
- Employee API (later phase)
- Authentication API (later phase)

## Phase 1 layout

```text
requirements.txt    Flask, pytest, and Waitress
.env.example        placeholder settings (copy to .env locally)
run.py              starts Flask
app/                application package (no business routes yet)
database/           schema.sql and seed.sql placeholders
tests/              automated tests come in later phases
```

The database connection in `app/db.py` is reserved for Phase 2. Do not commit `.env` or `database/ems.sqlite`.
