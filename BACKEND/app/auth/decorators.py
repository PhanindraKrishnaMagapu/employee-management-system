"""Reusable permission decorators for Flask endpoints.

All decorators return the same JSON error shape and mark the wrapped view as
protected so the application-wide default-deny guard can recognize it.
"""

from functools import wraps

from flask import jsonify

from app.auth.context import get_current_user


AUTHENTICATION_REQUIRED = "Authentication required"
PERMISSION_DENIED = "Permission denied"


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _validate_permissions(permissions, decorator_name):
    """Validate decorator configuration before it can protect a view.

    An empty list is rejected because ``all([])`` is True and would silently
    allow every authenticated caller. Non-string or blank names are rejected
    for the same reason: a typo must fail at configuration time.
    """

    permissions = tuple(permissions)
    if not permissions:
        raise ValueError(f"{decorator_name} requires at least one permission")
    if any(not isinstance(p, str) or not p.strip() for p in permissions):
        raise ValueError(
            f"{decorator_name} requires non-empty string permission names"
        )
    return permissions


def _mark_protected(view, permissions, auth_only):
    view._rbac_protected = True
    view._rbac_permissions = frozenset(permissions)
    view._rbac_auth_only = auth_only
    return view


def _check_user():
    """Return (user, error_response); exactly one value is non-None."""

    user = get_current_user()
    if user is None:
        return None, _error(AUTHENTICATION_REQUIRED, 401)
    return user, None


def require_authentication(view=None):
    """Require a valid session without requiring a specific permission."""

    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            _, error = _check_user()
            if error is not None:
                return error
            return function(*args, **kwargs)

        return _mark_protected(wrapped, (), True)

    if view is None:
        return decorator
    return decorator(view)


def require_permission(permission):
    """Require one specific permission."""

    permission = _validate_permissions((permission,), "require_permission")[0]

    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            user, error = _check_user()
            if error is not None:
                return error
            if permission not in user.permissions:
                return _error(PERMISSION_DENIED, 403)
            return function(*args, **kwargs)

        return _mark_protected(wrapped, (permission,), False)

    return decorator


def require_any_permission(*permissions):
    """Require at least one of the supplied permissions."""

    permissions = _validate_permissions(permissions, "require_any_permission")

    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            user, error = _check_user()
            if error is not None:
                return error
            if not any(p in user.permissions for p in permissions):
                return _error(PERMISSION_DENIED, 403)
            return function(*args, **kwargs)

        return _mark_protected(wrapped, permissions, False)

    return decorator


def require_all_permissions(*permissions):
    """Require every supplied permission."""

    permissions = _validate_permissions(permissions, "require_all_permissions")

    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            user, error = _check_user()
            if error is not None:
                return error
            if not all(p in user.permissions for p in permissions):
                return _error(PERMISSION_DENIED, 403)
            return function(*args, **kwargs)

        return _mark_protected(wrapped, permissions, False)

    return decorator
