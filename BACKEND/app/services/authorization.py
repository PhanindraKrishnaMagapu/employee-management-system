"""Employee record scope helpers used by RBAC-protected endpoints.

Permissions decide *what action* a role may take. These helpers decide *which
employee records* that action may touch. Endpoint-level denial is handled by
the decorators (403); a record outside the caller's scope is reported as 404
so its existence is not disclosed.

Project Manager project scoping is deliberately not implemented here.
"""

from flask import abort

from app.auth.permissions import (
    ROLE_CEO,
    ROLE_DEPARTMENT_MANAGER,
    ROLE_HR_ADMIN,
)


# A reporting chain is walked iteratively. The visited set stops manager
# cycles; the depth cap stops an excessively deep or corrupt chain.
MAX_SUBTREE_DEPTH = 25

# Future employee serializers must use an explicit allowlist. Restricted
# fields are listed here so they cannot be added by accident later.
RESTRICTED_EMPLOYEE_FIELDS = frozenset({
    "date_of_birth",
    "emergency_contact",
    "exit_reason",
})
SALARY_FIELDS = frozenset({
    "annual_salary",
    "currency",
    "effective_from",
    "effective_to",
})

EMPLOYEE_PUBLIC_FIELDS = (
    "id",
    "employee_code",
    "first_name",
    "last_name",
    "official_email",
    "phone",
    "joining_date",
    "employment_type",
    "employment_status",
    "location",
    "department_id",
    "designation_id",
    "manager_id",
    "profile_photo_path",
)


def _has_org_wide_read(user):
    return user is not None and (
        ROLE_HR_ADMIN in user.roles or ROLE_CEO in user.roles
    )


def get_linked_employee_id(user):
    """Return the employee id linked to the user, or None."""

    return user.employee_id if user is not None else None


def reporting_subtree(employee_id, connection):
    """Return an employee's full reporting subtree, including themselves.

    A visited set makes cyclic manager relationships harmless. Traversal
    stops after MAX_SUBTREE_DEPTH levels, so a corrupt chain cannot cause an
    unbounded loop.
    """

    if employee_id is None:
        return frozenset()

    children = {}
    for row in connection.execute("SELECT id, manager_id FROM employees"):
        children.setdefault(row["manager_id"], []).append(row["id"])

    visited = {employee_id}
    frontier = [employee_id]
    depth = 0

    while frontier and depth < MAX_SUBTREE_DEPTH:
        depth += 1
        next_level = []
        for manager_id in frontier:
            for child_id in children.get(manager_id, ()):
                if child_id not in visited:
                    visited.add(child_id)
                    next_level.append(child_id)
        frontier = next_level

    return frozenset(visited)


def employee_scope(user, connection):
    """Return visible employee ids, or None when the role is unrestricted.

    HR Admin and CEO read across the organization. Department Managers see
    their full reporting subtree. Employee and HR Executive see only their
    own linked record. A user without a linked employee record gets an empty
    scope unless their role is organization-wide.
    """

    if user is None:
        return frozenset()

    if _has_org_wide_read(user):
        return None

    employee_id = get_linked_employee_id(user)
    if employee_id is None:
        return frozenset()

    scope = {employee_id}
    if ROLE_DEPARTMENT_MANAGER in user.roles:
        scope.update(reporting_subtree(employee_id, connection))

    return frozenset(scope)


def can_access_employee(user, employee_id, connection):
    """Return True when the user may access this employee record."""

    if user is None or employee_id is None:
        return False

    # The record may not exist; the caller checks existence first so that a
    # missing record and an out-of-scope record both produce 404.
    scope = employee_scope(user, connection)
    return scope is None or employee_id in scope


def require_employee_access(user, employee_id, connection):
    """Abort with 404 when an employee record is outside the user's scope."""

    if not can_access_employee(user, employee_id, connection):
        abort(404)
