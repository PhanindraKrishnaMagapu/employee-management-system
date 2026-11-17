
# Employee Management System - UI

## Overview
This folder contains the frontend user interface of the Employee Management System.

## Technologies
- HTML
- CSS
- JavaScript

## Modules
- Employee Dashboard
- Employee List
- Add Employee
- Edit Employee
- Delete Employee
- Employee Profile

## Phase 1 layout

```text
index.html     placeholder home page
css/styles.css shared styles
js/api.js      future REST helper (base URL only for now)
js/auth.js     future login helper (empty for now)
pages/         feature screens arrive in later phases
```

The UI stays in this folder, separate from `BACKEND/`. Pages will call Flask with `fetch`. They will not open the SQLite file.
