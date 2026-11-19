"""Salary record validation, scope, history, and database helpers.

Salary data is confidential and lives outside the general employee API. This
module deliberately uses its own employee summary allowlist and its own scope
helper so that Payroll Admin never needs the general employee read grant.
"""

import math
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import abort

from app.auth.permissions import (
    PERMISSION_SALARY_MANAGE,
    PERMISSION_SALARY_READ,
    ROLE_PAYROLL_ADMIN,
)
from app.services import audit as audit_service
from app.services.authorization import employee_scope


SALARY_RECORD_FIELDS = (
    "id",
    "employee_id",
    "annual_salary",
    "monthly_gross_salary",
    "monthly_basic_salary",
    "monthly_hra",
    "monthly_allowances",
    "monthly_deductions",
    "currency",
    "effective_from",
    "effective_to",
    "created_at",
    "updated_at",
)

# Minimal identity fields needed to understand a salary record. This is
# intentionally narrower than EMPLOYEE_PUBLIC_FIELDS and never contains
# restricted employee data or any salary field.
SALARY_EMPLOYEE_FIELDS = (
    "id",
    "employee_code",
    "first_name",
    "last_name",
    "official_email",
    "employment_status",
    "department_id",
    "designation_id",
)

SALARY_CREATE_FIELDS = frozenset({
    "employee_id",
    "annual_salary",
    "monthly_gross_salary",
    "monthly_basic_salary",
    "monthly_hra",
    "monthly_allowances",
    "monthly_deductions",
    "currency",
    "effective_from",
    "effective_to",
})
SALARY_UPDATE_FIELDS = frozenset({
    "annual_salary",
    "monthly_gross_salary",
    "monthly_basic_salary",
    "monthly_hra",
    "monthly_allowances",
    "monthly_deductions",
    "currency",
    "effective_from",
    "effective_to",
})
SALARY_COMPONENT_FIELDS = (
    "monthly_gross_salary",
    "monthly_basic_salary",
    "monthly_hra",
    "monthly_allowances",
    "monthly_deductions",
)

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
DEFAULT_CURRENCY = "INR"
MAX_ANNUAL_SALARY = 1_000_000_000.0
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
MAX_SEARCH_LENGTH = 200

OPEN_ENDED_END = "9999-12-31"

# Audit metadata is deliberately limited to non-sensitive identifiers.
SALARY_AUDIT_TABLE = "salary_records"
SALARY_AUDIT_CREATE = "salary.create"
SALARY_AUDIT_UPDATE = "salary.update"


class SalaryValidationError(ValueError):
    """Raised when a salary payload or query parameter is invalid."""


def _columns(fields, prefix=None):
    if prefix is None:
        return ", ".join(fields)
    return ", ".join(f"{prefix}.{field} AS {field}" for field in fields)


def _employee_columns(prefix="e"):
    return ", ".join(
        f"{prefix}.{field} AS emp_{field}" for field in SALARY_EMPLOYEE_FIELDS
    )


def _placeholders(values):
    return ", ".join("?" for _ in values)


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _unknown_fields(payload, allowed_fields):
    unknown = set(payload) - set(allowed_fields)
    if unknown:
        raise SalaryValidationError(
            "Unsupported field(s): " + ", ".join(sorted(unknown))
        )


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SalaryValidationError(f"{field} must be a positive integer")
    return value


def _positive_int_param(value, field):
    text = str(value).strip()
    if not text or not text.isdigit() or int(text) <= 0:
        raise SalaryValidationError(f"{field} must be a positive integer")
    return int(text)


def _non_negative_int_param(value, field):
    text = str(value).strip()
    if not text or not text.isdigit():
        raise SalaryValidationError(f"{field} must be a non-negative integer")
    return int(text)


def _annual_salary(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SalaryValidationError(
            "annual_salary must be a non-negative finite number"
        )
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise SalaryValidationError(
            "annual_salary must be a non-negative finite number"
        )
    if number > MAX_ANNUAL_SALARY:
        raise SalaryValidationError(
            f"annual_salary must not exceed {MAX_ANNUAL_SALARY:.0f}"
        )
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise SalaryValidationError(
            "annual_salary must be a non-negative finite number"
        ) from error
    if decimal_value.as_tuple().exponent < -2:
        raise SalaryValidationError(
            "annual_salary must have at most two decimal places"
        )
    return number


def _optional_salary_component(value, field):
    if value is None:
        return None
    try:
        return _annual_salary(value)
    except SalaryValidationError as error:
        raise SalaryValidationError(
            f"{field} must be a non-negative finite amount with at most two decimal places"
        ) from error


def _currency(value):
    if not isinstance(value, str):
        raise SalaryValidationError("currency must be a three-letter code")
    currency = value.strip().upper()
    if not CURRENCY_PATTERN.fullmatch(currency):
        raise SalaryValidationError("currency must be a three-letter code")
    return currency


def _date(value, field):
    if not isinstance(value, str):
        raise SalaryValidationError(f"{field} must be a YYYY-MM-DD date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise SalaryValidationError(
            f"{field} must be a valid YYYY-MM-DD date"
        ) from error
    if parsed.isoformat() != value:
        raise SalaryValidationError(f"{field} must be a valid YYYY-MM-DD date")
    return value


def _optional_date(value, field):
    if _blank(value):
        return None
    return _date(value, field)


def validate_create_payload(payload):
    """Validate and normalize a salary record create payload."""

    if not isinstance(payload, dict):
        raise SalaryValidationError("Request body must be a JSON object")
    _unknown_fields(payload, SALARY_CREATE_FIELDS)

    missing = [
        field for field in ("employee_id", "annual_salary", "effective_from")
        if _blank(payload.get(field))
    ]
    if missing:
        raise SalaryValidationError(
            "Missing required field(s): " + ", ".join(missing)
        )

    effective_from = _date(payload["effective_from"], "effective_from")
    effective_to = _optional_date(payload.get("effective_to"), "effective_to")
    if effective_to is not None and effective_to < effective_from:
        raise SalaryValidationError(
            "effective_to must be on or after effective_from"
        )

    currency = (
        DEFAULT_CURRENCY
        if _blank(payload.get("currency"))
        else _currency(payload["currency"])
    )

    values = {
        "employee_id": _positive_int(payload["employee_id"], "employee_id"),
        "annual_salary": _annual_salary(payload["annual_salary"]),
        "currency": currency,
        "effective_from": effective_from,
        "effective_to": effective_to,
    }
    for field in SALARY_COMPONENT_FIELDS:
        values[field] = _optional_salary_component(payload.get(field), field)
    return values


def validate_update_payload(payload, current):
    """Validate and normalize a partial salary record update payload."""

    if not isinstance(payload, dict):
        raise SalaryValidationError("Request body must be a JSON object")
    _unknown_fields(payload, SALARY_UPDATE_FIELDS)
    if not payload:
        raise SalaryValidationError("At least one field is required")

    values = {}
    if "annual_salary" in payload:
        values["annual_salary"] = _annual_salary(payload["annual_salary"])
    if "currency" in payload:
        values["currency"] = _currency(payload["currency"])
    if "effective_from" in payload:
        values["effective_from"] = _date(
            payload["effective_from"], "effective_from"
        )
    if "effective_to" in payload:
        values["effective_to"] = _optional_date(
            payload["effective_to"], "effective_to"
        )
    for field in SALARY_COMPONENT_FIELDS:
        if field in payload:
            values[field] = _optional_salary_component(payload[field], field)

    effective_from = values.get("effective_from", current["effective_from"])
    effective_to = values.get("effective_to", current["effective_to"])
    if effective_to is not None and effective_to < effective_from:
        raise SalaryValidationError(
            "effective_to must be on or after effective_from"
        )
    return values


def parse_list_query(args):
    """Validate and normalize salary list query parameters."""

    filters = {
        "employee_id": None,
        "search": None,
        "currency": None,
        "active_on": None,
        "effective_from": None,
        "effective_to": None,
        "limit": DEFAULT_LIMIT,
        "offset": 0,
    }

    raw_employee = args.get("employee_id")
    if not _blank(raw_employee):
        filters["employee_id"] = _positive_int_param(
            raw_employee, "employee_id"
        )

    raw_search = args.get("search")
    if not _blank(raw_search):
        search = raw_search.strip()
        if len(search) > MAX_SEARCH_LENGTH:
            raise SalaryValidationError("search is too long")
        filters["search"] = search

    raw_currency = args.get("currency")
    if not _blank(raw_currency):
        filters["currency"] = _currency(raw_currency)

    for name in ("active_on", "effective_from", "effective_to"):
        raw_value = args.get(name)
        if not _blank(raw_value):
            filters[name] = _date(raw_value.strip(), name)

    raw_limit = args.get("limit")
    if not _blank(raw_limit):
        limit = _non_negative_int_param(raw_limit, "limit")
        if limit < 1:
            raise SalaryValidationError("limit must be a positive integer")
        filters["limit"] = min(limit, MAX_LIMIT)

    raw_offset = args.get("offset")
    if not _blank(raw_offset):
        filters["offset"] = _non_negative_int_param(raw_offset, "offset")

    return filters


def salary_employee_scope(user, connection):
    """Return salary-visible employee ids, or None for an authorized org role.

    Payroll Admin deliberately has no general employee permission. Reusing the
    shared employee_scope() would return an empty set and break every salary
    request, so Payroll Admin's explicit read grant remains organization-wide.
    HR Admin also receives organization-wide visibility through the existing
    employee_scope rule. General employee endpoints are unaffected.
    """

    if user is None:
        return frozenset()

    if ROLE_PAYROLL_ADMIN in user.roles and PERMISSION_SALARY_READ in user.permissions:
        return None

    return employee_scope(user, connection)


def can_access_salary_employee(user, employee_id, connection):
    """Return True when the employee is inside the salary scope."""

    if user is None or employee_id is None:
        return False
    scope = salary_employee_scope(user, connection)
    return scope is None or employee_id in scope


def require_salary_employee_access(user, employee_id, connection):
    """Abort with 404 when an employee is outside the salary scope."""

    if not can_access_salary_employee(user, employee_id, connection):
        abort(404)


def get_salary_employee(connection, employee_id):
    """Return the minimal salary employee row, including archived status."""

    return connection.execute(
        f"SELECT {_columns(SALARY_EMPLOYEE_FIELDS)}, archived_at "
        "FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()


def is_archived(employee_row):
    """Return True when the employee row has been archived."""

    return employee_row is not None and employee_row["archived_at"] is not None


def serialize_employee(row):
    """Build the minimal employee summary used inside salary responses."""

    return {field: row[field] for field in SALARY_EMPLOYEE_FIELDS}


def _serialize_joined(row):
    salary = {field: row[field] for field in SALARY_RECORD_FIELDS}
    salary["employee"] = {
        field: row["emp_" + field] for field in SALARY_EMPLOYEE_FIELDS
    }
    return salary


def _escape_like(value):
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _search_clause(alias, term):
    pattern = "%" + _escape_like(term) + "%"
    clause = (
        f"({alias}.employee_code LIKE ? ESCAPE '\\' "
        f"OR {alias}.first_name LIKE ? ESCAPE '\\' "
        f"OR {alias}.last_name LIKE ? ESCAPE '\\' "
        f"OR {alias}.official_email LIKE ? ESCAPE '\\')"
    )
    return clause, [pattern, pattern, pattern, pattern]


def list_salaries(connection, scope, filters):
    """Return serialized salary rows and the total count before pagination."""

    if scope is not None and not scope:
        return [], 0

    where = []
    parameters = []

    if filters["employee_id"] is not None:
        where.append("s.employee_id = ?")
        parameters.append(filters["employee_id"])
    if filters["search"]:
        clause, search_parameters = _search_clause("e", filters["search"])
        where.append(clause)
        parameters.extend(search_parameters)
    if filters["currency"]:
        where.append("s.currency = ?")
        parameters.append(filters["currency"])
    if filters["active_on"]:
        where.append(
            "s.effective_from <= ? "
            "AND (s.effective_to IS NULL OR s.effective_to >= ?)"
        )
        parameters.extend([filters["active_on"], filters["active_on"]])
    if filters["effective_from"]:
        where.append("s.effective_from >= ?")
        parameters.append(filters["effective_from"])
    if filters["effective_to"]:
        where.append("s.effective_from <= ?")
        parameters.append(filters["effective_to"])
    if scope is not None:
        scope_ids = sorted(scope)
        where.append(f"s.employee_id IN ({_placeholders(scope_ids)})")
        parameters.extend(scope_ids)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    base = (
        " FROM salary_records s "
        "JOIN employees e ON e.id = s.employee_id" + where_sql
    )

    total = connection.execute(
        "SELECT COUNT(*) AS total" + base, tuple(parameters)
    ).fetchone()["total"]

    rows = connection.execute(
        f"SELECT {_columns(SALARY_RECORD_FIELDS, 's')}, {_employee_columns('e')}"
        + base
        + " ORDER BY s.effective_from DESC, s.id DESC LIMIT ? OFFSET ?",
        tuple(parameters) + (filters["limit"], filters["offset"]),
    ).fetchall()

    return [_serialize_joined(row) for row in rows], total


def list_salary_employees(connection, scope, search=None):
    """Return non-archived employees for the salary form picker."""

    if scope is not None and not scope:
        return []

    where = ["e.archived_at IS NULL"]
    parameters = []
    if search:
        clause, search_parameters = _search_clause("e", search)
        where.append(clause)
        parameters.extend(search_parameters)
    if scope is not None:
        scope_ids = sorted(scope)
        where.append(f"e.id IN ({_placeholders(scope_ids)})")
        parameters.extend(scope_ids)

    rows = connection.execute(
        f"SELECT {_columns(SALARY_EMPLOYEE_FIELDS, 'e')} FROM employees e "
        "WHERE " + " AND ".join(where) +
        " ORDER BY e.employee_code COLLATE NOCASE, e.id",
        tuple(parameters),
    ).fetchall()
    return [serialize_employee(row) for row in rows]


def get_salary(connection, salary_id):
    """Return one serialized salary record, or None."""

    row = connection.execute(
        f"SELECT {_columns(SALARY_RECORD_FIELDS, 's')}, {_employee_columns('e')} "
        "FROM salary_records s "
        "JOIN employees e ON e.id = s.employee_id "
        "WHERE s.id = ?",
        (salary_id,),
    ).fetchone()
    return _serialize_joined(row) if row is not None else None


def find_overlapping_salary(
    connection, employee_id, effective_from, effective_to, exclude_id=None
):
    """Return one overlapping salary record, or None.

    Salary periods are inclusive. An open-ended period is treated as ending
    at OPEN_ENDED_END so text date comparison remains correct.
    """

    upper_bound = effective_to or OPEN_ENDED_END
    sql = (
        "SELECT id FROM salary_records "
        "WHERE employee_id = ? "
        "AND effective_from <= ? "
        "AND (effective_to IS NULL OR effective_to >= ?)"
    )
    parameters = [employee_id, upper_bound, effective_from]
    if exclude_id is not None:
        sql += " AND id <> ?"
        parameters.append(exclude_id)
    sql += " ORDER BY effective_from, id LIMIT 1"
    return connection.execute(sql, tuple(parameters)).fetchone()


def close_open_salary_records(connection, employee_id, new_effective_from):
    """Close earlier open-ended periods the day before a new period starts.

    This preserves salary history instead of deleting it. Only records that
    start strictly before the new period are closed; later open-ended records
    are left for the overlap check to reject. The ids of the closed records are
    returned so the caller can audit each automatic close.
    """

    previous_day = (
        date.fromisoformat(new_effective_from) - timedelta(days=1)
    ).isoformat()
    rows = connection.execute(
        "SELECT id FROM salary_records "
        "WHERE employee_id = ? AND effective_to IS NULL "
        "AND effective_from < ? "
        "ORDER BY effective_from, id",
        (employee_id, new_effective_from),
    ).fetchall()
    closed_ids = [row["id"] for row in rows]
    if not closed_ids:
        return closed_ids

    connection.execute(
        "UPDATE salary_records SET effective_to = ?, "
        "updated_at = CURRENT_TIMESTAMP "
        f"WHERE id IN ({_placeholders(closed_ids)})",
        (previous_day, *closed_ids),
    )
    return closed_ids


def log_salary_audit(connection, actor_user_id, action, salary):
    """Write one safe salary audit row for a successful create or update.

    Only the actor, action, table name, salary record id, and employee id are
    stored. Salary amounts, currency, effective dates, bank details, and tax
    information are never written to the audit log.
    """

    audit_service.write_event(
        connection,
        actor_user_id=actor_user_id,
        action=action,
        table_name=SALARY_AUDIT_TABLE,
        record_id=salary["id"],
        summary=audit_service.employee_only_summary(salary["employee_id"]),
    )


def log_salary_create(connection, actor_user_id, salary):
    """Audit a successful salary record creation."""

    log_salary_audit(
        connection, actor_user_id, SALARY_AUDIT_CREATE, salary
    )


def log_salary_update(connection, actor_user_id, salary):
    """Audit a successful salary record update, including archived corrections."""

    log_salary_audit(
        connection, actor_user_id, SALARY_AUDIT_UPDATE, salary
    )


def log_salary_auto_close(
    connection, actor_user_id, employee_id, salary_id
):
    """Audit an earlier salary record closed by a newer creation.

    The closed record no longer needs to be read because only its identifier
    and owning employee id are written; no salary values are stored.
    """

    audit_service.write_event(
        connection,
        actor_user_id=actor_user_id,
        action=SALARY_AUDIT_UPDATE,
        table_name=SALARY_AUDIT_TABLE,
        record_id=salary_id,
        summary=audit_service.employee_only_summary(employee_id),
    )


def create_salary(connection, values):
    """Insert a salary record in the caller's transaction."""

    columns = (
        "employee_id",
        "annual_salary",
        *SALARY_COMPONENT_FIELDS,
        "currency",
        "effective_from",
        "effective_to",
    )
    parameters = tuple(values.get(field) for field in columns)
    cursor = connection.execute(
        f"INSERT INTO salary_records ({_columns(columns)}) "
        f"VALUES ({_placeholders(parameters)})",
        parameters,
    )
    return get_salary(connection, cursor.lastrowid)


def update_salary(connection, salary_id, values):
    """Update allowed salary fields in the caller's transaction."""

    assignments = [f"{field} = ?" for field in values]
    parameters = list(values.values()) + [salary_id]
    connection.execute(
        "UPDATE salary_records SET " + ", ".join(assignments) +
        ", updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(parameters),
    )
    return get_salary(connection, salary_id)
