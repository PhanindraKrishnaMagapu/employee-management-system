"""Safety checks for the isolated Render demo entry point."""

import sqlite3

import pytest

import render
from app.config import Config
from app.services.auth import authenticate_user


def _set_demo_environment(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "render-test-secret-key")
    monkeypatch.setenv("DEMO_ADMIN_USERNAME", "hosted_demo_admin")
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "hosted-admin@example.invalid")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "TestHostedDemo!234")


def _database_snapshot(database_path):
    connection = sqlite3.connect(database_path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
        employees = connection.execute(
            "SELECT employee_code, first_name, last_name, official_email "
            "FROM employees ORDER BY id"
        ).fetchall()
        hosted_user = connection.execute(
            """
            SELECT u.username, u.email, u.is_active, r.name
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            WHERE u.username = 'hosted_demo_admin'
            ORDER BY r.name
            """
        ).fetchall()
        return counts, employees, hosted_user
    finally:
        connection.close()


def test_create_demo_app_uses_temp_db_and_provisions_only_demo_login(
    monkeypatch, tmp_path
):
    _set_demo_environment(monkeypatch)
    monkeypatch.setattr(Config, "DATABASE_PATH", Config.DATABASE_PATH)
    monkeypatch.setattr(render.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "local-ems.sqlite"))

    application = render.create_demo_app()

    hosted_path = tmp_path / render.DEMO_DATABASE_DIRECTORY / "ems.sqlite"
    assert application.config["DEBUG"] is False
    assert application.config["DATABASE_PATH"] == str(hosted_path)
    assert not (tmp_path / "local-ems.sqlite").exists()
    assert authenticate_user("hosted_demo_admin", "TestHostedDemo!234")["roles"] == [
        "HR Admin"
    ]
    assert authenticate_user("demo_hr_admin", "NOT_A_REAL_PASSWORD_HASH") is None

    connection = sqlite3.connect(hosted_path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0] == 3
        assert connection.execute(
            "SELECT COUNT(*) FROM salary_records"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_create_demo_app_is_safe_to_run_twice(monkeypatch, tmp_path):
    _set_demo_environment(monkeypatch)
    monkeypatch.setattr(Config, "DATABASE_PATH", Config.DATABASE_PATH)
    monkeypatch.setattr(render.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "local-ems.sqlite"))

    first_app = render.create_demo_app()
    hosted_path = first_app.config["DATABASE_PATH"]
    first_snapshot = _database_snapshot(hosted_path)

    second_app = render.create_demo_app()
    second_snapshot = _database_snapshot(second_app.config["DATABASE_PATH"])

    assert second_app.config["DATABASE_PATH"] == hosted_path
    assert second_snapshot == first_snapshot
    assert first_snapshot[0]["employees"] == 7
    assert first_snapshot[0]["salary_records"] == 0
    assert first_snapshot[0]["schema_migrations"] == 3
    assert first_snapshot[0]["users"] == 8
    assert first_snapshot[1] == [
        ("DEMO001", "Alex", "Morgan", "alex.morgan@example.invalid"),
        ("DEMO002", "Taylor", "Sharma", "taylor.sharma@example.invalid"),
        ("DEMO003", "Jordan", "Reddy", "jordan.reddy@example.invalid"),
        ("DEMO004", "Casey", "Kumar", "casey.kumar@example.invalid"),
        ("DEMO005", "Riley", "Patel", "riley.patel@example.invalid"),
        ("DEMO006", "Avery", "Rao", "avery.rao@example.invalid"),
        ("DEMO007", "Jamie", "Das", "jamie.das@example.invalid"),
    ]
    assert first_snapshot[2] == [
        ("hosted_demo_admin", "hosted-admin@example.invalid", 1, "HR Admin")
    ]
    assert authenticate_user("hosted_demo_admin", "TestHostedDemo!234")
    assert not (tmp_path / "local-ems.sqlite").exists()


def test_startup_logs_do_not_expose_configured_credentials(
    monkeypatch, tmp_path, capsys, caplog
):
    secret_values = {
        "FLASK_SECRET_KEY": "render-secret-log-check-4a82b1",
        "DEMO_ADMIN_USERNAME": "private-demo-user-4a82b1",
        "DEMO_ADMIN_EMAIL": "private-demo-4a82b1@example.invalid",
        "DEMO_ADMIN_PASSWORD": "private-password-log-check-4a82b1",
    }
    for name, value in secret_values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(Config, "DATABASE_PATH", Config.DATABASE_PATH)
    monkeypatch.setattr(render.tempfile, "tempdir", str(tmp_path))

    render.create_demo_app()

    captured = capsys.readouterr()
    application_logs = captured.out + captured.err + caplog.text
    for value in secret_values.values():
        assert value not in application_logs


def test_missing_production_secret_fails_before_database_initialization(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    monkeypatch.setenv("DEMO_ADMIN_USERNAME", "hosted_demo_admin")
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "hosted-admin@example.invalid")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "TestHostedDemo!234")
    monkeypatch.setattr(Config, "DATABASE_PATH", Config.DATABASE_PATH)
    monkeypatch.setattr(render.tempfile, "tempdir", str(tmp_path))

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        render.create_demo_app()

    assert not (tmp_path / render.DEMO_DATABASE_DIRECTORY).exists()


def test_missing_demo_credentials_fails_startup(monkeypatch, tmp_path):
    monkeypatch.setenv("FLASK_SECRET_KEY", "render-test-secret-key")
    monkeypatch.delenv("DEMO_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("DEMO_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(Config, "DATABASE_PATH", Config.DATABASE_PATH)
    monkeypatch.setattr(render.tempfile, "tempdir", str(tmp_path))

    with pytest.raises(RuntimeError, match="DEMO_ADMIN_USERNAME"):
        render.create_demo_app()


def test_main_serves_waitress_on_render_port(monkeypatch):
    served = {}

    monkeypatch.setattr(render, "create_demo_app", lambda: object())
    monkeypatch.setenv("PORT", "12345")
    monkeypatch.setattr(
        "waitress.serve",
        lambda application, **kwargs: served.update(
            application=application, **kwargs
        ),
    )

    render.main()

    assert served == {
        "application": served["application"],
        "host": "0.0.0.0",
        "port": 12345,
    }
