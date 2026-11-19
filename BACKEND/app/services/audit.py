"""Safe audit-log writing for sensitive business actions.

Audit rows deliberately store only non-sensitive metadata. Callers that handle
confidential data must pass a summary that contains no amounts, currency,
effective dates, bank details, tax information, or other business values.
"""

import json


def write_event(
    connection, actor_user_id, action, table_name, record_id, summary=None
):
    """Insert one audit row inside the caller's transaction.

    The caller owns the transaction so a failed business write cannot leave a
    misleading audit entry behind.
    """

    connection.execute(
        "INSERT INTO audit_logs "
        "(actor_user_id, action, table_name, record_id, summary) "
        "VALUES (?, ?, ?, ?, ?)",
        (actor_user_id, action, table_name, record_id, summary),
    )


def employee_only_summary(employee_id):
    """Return the safe salary audit summary: the employee id and nothing else."""

    return json.dumps(
        {"employee_id": int(employee_id)},
        sort_keys=True,
        separators=(",", ":"),
    )
