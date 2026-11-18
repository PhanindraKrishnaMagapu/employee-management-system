"""Canonical RBAC permission names and the role-to-permission mapping.

Permissions are code constants, not database rows. Role names are the values
stored in the ``roles`` table. This module is the single source of truth for
what a role may do; unknown roles deliberately receive no permissions so that
a new or renamed role fails closed.
"""

# Role names as stored in the seeded roles table.
ROLE_CEO = "CEO"
ROLE_HR_ADMIN = "HR Admin"
ROLE_HR_EXECUTIVE = "HR Executive"
ROLE_DEPARTMENT_MANAGER = "Department Manager"
ROLE_PROJECT_MANAGER = "Project Manager"
ROLE_EMPLOYEE = "Employee"
ROLE_SYSTEM_ADMIN = "System Admin"
ROLE_PAYROLL_ADMIN = "Payroll Admin"

# Technical and administrative actions. These do not grant business data.
PERMISSION_USER_MANAGE = "users:manage"
PERMISSION_ROLE_MANAGE = "roles:manage"
PERMISSION_AUDIT_READ = "audit:read"

# Employee business data. Read scope is resolved separately by
# app.services.authorization; "all" bypasses record scope, "scope" obeys it.
PERMISSION_EMPLOYEE_READ_ALL = "employees:read:all"
PERMISSION_EMPLOYEE_READ_SCOPE = "employees:read:scope"
PERMISSION_EMPLOYEE_CREATE = "employees:create"
PERMISSION_EMPLOYEE_UPDATE = "employees:update"
PERMISSION_EMPLOYEE_UPDATE_LIMITED = "employees:update:limited"
PERMISSION_EMPLOYEE_ARCHIVE = "employees:archive"
PERMISSION_EMPLOYEE_SELF_UPDATE = "employees:update:self"

# Supporting organizational permissions.
PERMISSION_ORG_READ = "organization:read"
PERMISSION_JML_READ = "jml:read"
PERMISSION_JML_MANAGE = "jml:manage"
PERMISSION_PROJECT_READ = "projects:read"
PERMISSION_PROJECT_MANAGE = "projects:manage"
PERMISSION_REPORT_READ = "reports:read"

# Confidential salary data. Only Payroll Admin grants these permissions.
PERMISSION_SALARY_READ = "salary:read"
PERMISSION_SALARY_MANAGE = "salary:manage"


# Central role -> permission map. Every seeded role is intentionally listed.
ROLE_PERMISSIONS = {
    # Organization-wide read-only reporting; no writes and no salary.
    ROLE_CEO: frozenset({
        PERMISSION_EMPLOYEE_READ_ALL,
        PERMISSION_ORG_READ,
        PERMISSION_JML_READ,
        PERMISSION_PROJECT_READ,
        PERMISSION_REPORT_READ,
    }),
    # Employee lifecycle and HR operations; salary requires an extra grant.
    ROLE_HR_ADMIN: frozenset({
        PERMISSION_EMPLOYEE_READ_ALL,
        PERMISSION_EMPLOYEE_CREATE,
        PERMISSION_EMPLOYEE_UPDATE,
        PERMISSION_EMPLOYEE_ARCHIVE,
        PERMISSION_ORG_READ,
        PERMISSION_JML_MANAGE,
        PERMISSION_PROJECT_READ,
        PERMISSION_REPORT_READ,
    }),
    # Limited HR work. Assigned-scope is not implemented yet, so record scope
    # is self-only for this role until department scoping is approved.
    ROLE_HR_EXECUTIVE: frozenset({
        PERMISSION_EMPLOYEE_READ_SCOPE,
        PERMISSION_EMPLOYEE_UPDATE_LIMITED,
        PERMISSION_ORG_READ,
        PERMISSION_JML_READ,
    }),
    # Full reporting subtree, never salary or user/role administration.
    ROLE_DEPARTMENT_MANAGER: frozenset({
        PERMISSION_EMPLOYEE_READ_SCOPE,
        PERMISSION_EMPLOYEE_UPDATE_LIMITED,
        PERMISSION_ORG_READ,
        PERMISSION_JML_READ,
        PERMISSION_PROJECT_READ,
    }),
    # Project database scope is deferred; these are permissions only.
    ROLE_PROJECT_MANAGER: frozenset({
        PERMISSION_PROJECT_READ,
        PERMISSION_PROJECT_MANAGE,
        PERMISSION_ORG_READ,
    }),
    # Own record and permitted self-service only.
    ROLE_EMPLOYEE: frozenset({
        PERMISSION_EMPLOYEE_READ_SCOPE,
        PERMISSION_EMPLOYEE_SELF_UPDATE,
        PERMISSION_ORG_READ,
    }),
    # Technical user/role administration only; no business data by default.
    ROLE_SYSTEM_ADMIN: frozenset({
        PERMISSION_USER_MANAGE,
        PERMISSION_ROLE_MANAGE,
        PERMISSION_AUDIT_READ,
    }),
    # Explicit salary grant only; never assigned automatically.
    ROLE_PAYROLL_ADMIN: frozenset({
        PERMISSION_SALARY_READ,
        PERMISSION_SALARY_MANAGE,
    }),
}

ALL_PERMISSIONS = frozenset().union(*ROLE_PERMISSIONS.values())


def _normalize_roles(roles):
    """Accept a single role name or an iterable of role names."""

    if roles is None:
        return ()
    if isinstance(roles, str):
        return (roles,)
    return tuple(roles)


def permissions_for_roles(roles):
    """Return the union of permissions for the given roles.

    Unknown roles contribute nothing. Multiple roles are additive: this RBAC
    foundation does not implement deny-overrides.
    """

    result = set()
    for role in _normalize_roles(roles):
        result.update(ROLE_PERMISSIONS.get(role, ()))
    return frozenset(result)


def has_permission(roles, permission):
    """Return True when the roles include one specific permission."""

    return permission in permissions_for_roles(roles)


def has_any_permission(roles, permissions):
    """Return True when at least one of the permissions is granted."""

    granted = permissions_for_roles(roles)
    return any(permission in granted for permission in permissions)


def has_all_permissions(roles, permissions):
    """Return True when every requested permission is granted."""

    granted = permissions_for_roles(roles)
    return all(permission in granted for permission in permissions)
