"""Tests for the development-only demo password provisioning command."""

import sqlite3

import pytest

from app.db import (
    DEMO_USERNAMES,
    PLACEHOLDER_PASSWORD_HASH,
    get_connection,
    is_valid_password_hash,
    provision_demo_passwords,
)
from app.services.auth import authenticate_user


def _stored_hashes():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT username, password_hash FROM users ORDER BY username"
        ).fetchall()
        return {row["username"]: row["password_hash"] for row in rows}
    finally:
        connection.close()


def _count(table):
    connection = get_connection()
    try:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()


def _all_rows(table):
    connection = get_connection()
    try:
        return [tuple(row) for row in connection.execute(
            f"SELECT * FROM {table} ORDER BY id"
        )]
    finally:
        connection.close()


def test_placeholder_accounts_are_provisioned(isolated_db):
    before_counts = {table: _count(table) for table in ("employees", "users", "user_roles")}

    result = provision_demo_passwords("TestDemo!234")

    assert sorted(result["updated"]) == sorted(DEMO_USERNAMES)
    assert result["skipped"] == []
    assert result["missing"] == []

    hashes = _stored_hashes()
    for username in DEMO_USERNAMES:
        assert hashes[username] != PLACEHOLDER_PASSWORD_HASH
        assert is_valid_password_hash(hashes[username])
        assert authenticate_user(username, "TestDemo!234") is not None

    assert {table: _count(table) for table in before_counts} == before_counts


def test_existing_valid_hashes_are_preserved_without_force(isolated_db):
    provision_demo_passwords("FirstDemo!234")
    before = _stored_hashes()

    result = provision_demo_passwords("SecondDemo!234")

    assert result["updated"] == []
    assert sorted(result["skipped"]) == sorted(DEMO_USERNAMES)
    assert _stored_hashes() == before
    assert all(authenticate_user(name, "FirstDemo!234") for name in DEMO_USERNAMES)
    assert not any(authenticate_user(name, "SecondDemo!234") for name in DEMO_USERNAMES)


def test_force_replaces_existing_hashes(isolated_db):
    provision_demo_passwords("FirstDemo!234")
    before = _stored_hashes()

    result = provision_demo_passwords("SecondDemo!234", force=True)

    assert sorted(result["updated"]) == sorted(DEMO_USERNAMES)
    after = _stored_hashes()
    assert all(after[name] != before[name] for name in DEMO_USERNAMES)
    assert all(authenticate_user(name, "SecondDemo!234") for name in DEMO_USERNAMES)


def test_only_demo_usernames_are_updated(isolated_db):
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ("outside_user", "outside@example.invalid", PLACEHOLDER_PASSWORD_HASH),
        )
        connection.commit()
    finally:
        connection.close()

    employees_before = _all_rows("employees")

    provision_demo_passwords("TestDemo!234")

    assert _stored_hashes()["outside_user"] == PLACEHOLDER_PASSWORD_HASH
    assert _all_rows("employees") == employees_before


def test_production_environment_refuses(monkeypatch, isolated_db):
    before = _stored_hashes()
    monkeypatch.setenv("FLASK_ENV", "production")

    with pytest.raises(RuntimeError, match="production"):
        provision_demo_passwords("TestDemo!234")

    assert _stored_hashes() == before


def test_empty_password_rejected(isolated_db):
    with pytest.raises(ValueError):
        provision_demo_passwords("")


def test_getpass_is_default_and_secrets_are_not_printed(monkeypatch, capsys, isolated_db):
    import app.db as db_module

    prompts = []

    def fake_getpass(prompt=""):
        prompts.append(prompt)
        return "HiddenDemo!987"

    monkeypatch.setattr(db_module.getpass, "getpass", fake_getpass)
    monkeypatch.setattr("sys.argv", ["app.db", "demo-passwords"])
    db_module.main()

    output = capsys.readouterr().out
    assert "HiddenDemo!987" not in output
    assert "scrypt" not in output
    assert "password_hash" not in output
    assert len(prompts) == 2
    assert all(authenticate_user(name, "HiddenDemo!987") for name in DEMO_USERNAMES)


def test_environment_password_requires_yes(monkeypatch, isolated_db):
    import app.db as db_module

    monkeypatch.setenv("EMS_TEST_DEMO_PASSWORD", "EnvDemo!567")

    monkeypatch.setattr(
        "sys.argv",
        ["app.db", "demo-passwords", "--password-env", "EMS_TEST_DEMO_PASSWORD"],
    )
    with pytest.raises(SystemExit) as excinfo:
        db_module.main()
    assert excinfo.value.code == 1
    assert all(
        _stored_hashes()[name] == PLACEHOLDER_PASSWORD_HASH
        for name in DEMO_USERNAMES
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "app.db",
            "demo-passwords",
            "--password-env",
            "EMS_TEST_DEMO_PASSWORD",
            "--yes",
        ],
    )
    db_module.main()
    assert all(authenticate_user(name, "EnvDemo!567") for name in DEMO_USERNAMES)


def test_rollback_on_hash_generation_failure(monkeypatch, isolated_db):
    import app.services.auth as auth_service

    before = _stored_hashes()
    original_hash = auth_service.hash_password
    calls = {"count": 0}

    def failing_hash(password):
        calls["count"] += 1
        if calls["count"] == 3:
            raise sqlite3.OperationalError("simulated hashing failure")
        return original_hash(password)

    monkeypatch.setattr(auth_service, "hash_password", failing_hash)

    with pytest.raises(sqlite3.OperationalError):
        provision_demo_passwords("TestDemo!234")

    assert calls["count"] == 3
    assert _stored_hashes() == before


def test_authentication_verification_failure_raises(monkeypatch, isolated_db):
    import app.services.auth as auth_service

    monkeypatch.setattr(auth_service, "authenticate_user", lambda name, pwd: None)

    with pytest.raises(RuntimeError, match="verification"):
        provision_demo_passwords("TestDemo!234")
