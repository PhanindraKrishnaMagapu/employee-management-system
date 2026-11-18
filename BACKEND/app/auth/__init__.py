"""Authentication and authorization building blocks.

Login/session handling lives in ``app.routes.auth`` and ``app.services.auth``.
This package holds the RBAC permission map, per-request user context, and the
decorators that protect endpoints.
"""

from app.auth.context import CurrentUser, get_current_user
from app.auth.decorators import (
    require_all_permissions,
    require_any_permission,
    require_authentication,
    require_permission,
)

__all__ = [
    "CurrentUser",
    "get_current_user",
    "require_all_permissions",
    "require_any_permission",
    "require_authentication",
    "require_permission",
]
