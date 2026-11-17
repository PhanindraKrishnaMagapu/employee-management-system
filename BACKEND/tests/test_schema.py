
import sqlite3

import pytest

from app.config import Config
from app.db import get_connection, initialize_database


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    """Create an isolated temporary database for each test."""
    database_path = tmp_path / "test_ems.sqlite"

    monkeypatch.setattr(Config, "DATABASE_PATH", str(database_path))

    initialize_database()

    return database_path


def test_all_tables_created(test_database):
    """Verify that all 15 application tables exist."""
    connection = get_connection()

    try:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

        assert len(tables) == 15
    finally:
        connection.close()


def test_foreign_keys_enabled(test_database):
    """Verify that foreign-key enforcement is enabled."""
    connection = get_connection()

    try:
        result = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        assert result == 1
    finally:
        connection.close()


def test_demo_data_inserted(test_database):
    """Verify that demo employees and users are inserted."""
    connection = get_connection()

    try:
        employee_count = connection.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        assert employee_count == 7
        assert user_count == 7
    finally:
        connection.close()


def test_duplicate_employee_code_rejected(test_database):
    """Verify that employee codes must be unique."""
    connection = get_connection()

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO employees (
                    employee_code,
                    first_name,
                    last_name,
                    official_email,
                    joining_date,
                    employment_type,
                    department_id,
                    designation_id
                )
                VALUES (
                    'DEMO001',
                    'Test',
                    'Employee',
                    'test.unique@example.invalid',
                    '2026-11-17',
                    'Full-time',
                    1,
                    1
                )
                """
            )
    finally:
        connection.close()


def test_salary_requires_existing_employee(test_database):
    """Verify that salary records require a valid employee."""
    connection = get_connection()

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO salary_records (
                    employee_id,
                    annual_salary,
                    currency,
                    effective_from
                )
                VALUES (
                    99999,
                    500000,
                    'INR',
                    '2026-11-17'
                )
                """
            )
    finally:
        connection.close()


def test_database_initialization_is_repeatable(test_database):
    """Verify that running initialization twice does not duplicate demo data."""
    initialize_database()

    connection = get_connection()

    try:
        employee_count = connection.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        assert employee_count == 7
        assert user_count == 7
    finally:
        connection.close()
