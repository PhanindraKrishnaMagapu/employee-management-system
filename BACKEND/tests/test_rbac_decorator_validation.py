"""Configuration-time validation tests for RBAC permission decorators."""

import pytest

from app.auth.decorators import (
    require_all_permissions,
    require_any_permission,
    require_permission,
)


MULTI_PERMISSION_DECORATORS = (require_all_permissions, require_any_permission)


@pytest.mark.parametrize("factory", MULTI_PERMISSION_DECORATORS)
def test_empty_permission_list_is_rejected(factory):
    with pytest.raises(ValueError, match="at least one permission"):
        factory()


def test_require_permission_cannot_be_called_without_a_name():
    with pytest.raises(TypeError):
        require_permission()


@pytest.mark.parametrize("factory", MULTI_PERMISSION_DECORATORS)
@pytest.mark.parametrize(
    "permission", ["", "   ", "\t\n", None, 123, b"users:manage", [], {}]
)
def test_invalid_permission_names_are_rejected(factory, permission):
    with pytest.raises(ValueError, match="non-empty string permission names"):
        factory(permission)


@pytest.mark.parametrize("permission", ["", "   ", None, 123, b"users:manage"])
def test_require_permission_rejects_invalid_names(permission):
    with pytest.raises(ValueError, match="non-empty string permission names"):
        require_permission(permission)


def test_mixed_valid_and_invalid_permissions_are_rejected():
    with pytest.raises(ValueError, match="non-empty string permission names"):
        require_all_permissions("users:manage", "")
    with pytest.raises(ValueError, match="non-empty string permission names"):
        require_any_permission("users:manage", None)


@pytest.mark.parametrize(
    "factory, permissions",
    [
        (require_permission, ("users:manage",)),
        (require_any_permission, ("users:manage", "salary:read")),
        (require_all_permissions, ("users:manage", "roles:manage")),
    ],
)
def test_valid_decorator_configuration_is_unchanged(factory, permissions):
    def view():
        return "ok"

    decorated = factory(*permissions)(view)

    assert decorated is not view
    assert decorated.__name__ == "view"
    assert decorated._rbac_protected is True
    assert decorated._rbac_permissions == frozenset(permissions)
