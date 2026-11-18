"""Per-request authenticated-user context for authorization checks.

The session holds only ``user_id``. Roles and permissions are always loaded
from the database on each request and cached in ``flask.g`` for that request
only. They are never written back to the session.
"""

from dataclasses import dataclass

from flask import g, session

from app.auth.permissions import permissions_for_roles
from app.db import get_connection


_CONTEXT_KEY = "_rbac_current_user"


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user data needed by authorization decisions."""

    id: int
    username: str
    email: str
    roles: tuple
    employee_id: int | None
    permissions: frozenset


def get_current_user():
    """Return the current user, or None when the session is not valid.

    The result (including None) is cached in ``flask.g`` so a request that
    calls this more than once performs only one set of database queries.
    """

    if hasattr(g, _CONTEXT_KEY):
        return getattr(g, _CONTEXT_KEY)

    user = _load_current_user()
    setattr(g, _CONTEXT_KEY, user)
    return user


def _load_current_user():
    user_id = session.get("user_id")
    if user_id is None or isinstance(user_id, bool):
        return None

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        session.clear()
        return None

    connection = get_connection()

    try:
        # Explicit columns only: sensitive fields must never leak into a
        # generic user object, and SELECT * is avoided by design.
        row = connection.execute(
            """
            SELECT id, username, email, employee_id
            FROM users
            WHERE id = ? AND is_active = 1
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            session.clear()
            return None

        role_rows = connection.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = ?
            ORDER BY r.name
            """,
            (user_id,),
        ).fetchall()
    finally:
        connection.close()

    roles = tuple(role["name"] for role in role_rows)

    return CurrentUser(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        employee_id=row["employee_id"],
        roles=roles,
        permissions=permissions_for_roles(roles),
    )
