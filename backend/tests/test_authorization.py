"""Role-based access control and tenant isolation.

Every assertion here is about the *server's* decision. The frontend hides
controls the user cannot use, but these tests bypass the UI entirely.
"""

from __future__ import annotations

import pytest

from app.models import Role
from app.security.rbac import Permission, ROLE_PERMISSIONS

pytestmark = pytest.mark.security


async def _create_group(authed, name="Test Group"):
    response = await authed.post("/api/v1/groups", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------
def test_role_permissions_are_strictly_nested():
    """A higher role must never lose a permission a lower role has."""
    assert ROLE_PERMISSIONS[Role.USER] <= ROLE_PERMISSIONS[Role.EDITOR]
    assert ROLE_PERMISSIONS[Role.EDITOR] <= ROLE_PERMISSIONS[Role.ADMIN]
    assert ROLE_PERMISSIONS[Role.ADMIN] <= ROLE_PERMISSIONS[Role.SUPER_ADMIN]


def test_only_super_admin_holds_system_admin():
    for role in (Role.USER, Role.EDITOR, Role.ADMIN):
        assert Permission.SYSTEM_ADMIN not in ROLE_PERMISSIONS[role]
    assert Permission.SYSTEM_ADMIN in ROLE_PERMISSIONS[Role.SUPER_ADMIN]


def test_editor_cannot_delete_groups_or_manage_members():
    editor = ROLE_PERMISSIONS[Role.EDITOR]
    assert Permission.GROUP_DELETE_ANY not in editor
    assert Permission.ORG_MEMBER_MANAGE not in editor
    assert Permission.ROLE_ASSIGN not in editor
    assert Permission.AUDIT_READ not in editor


def test_plain_user_cannot_touch_other_peoples_resources():
    user = ROLE_PERMISSIONS[Role.USER]
    assert Permission.GROUP_UPDATE_ANY not in user
    assert Permission.LINK_MANAGE_ANY not in user
    assert Permission.ANALYTICS_READ_ANY not in user


# ---------------------------------------------------------------------------
# Group ownership
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_member_cannot_see_another_members_group(member_client, make_user, sign_in):
    owned = await _create_group(member_client, "Private Group")

    other = await sign_in(await make_user(Role.USER))
    # Not-found rather than forbidden: the id must not be confirmable.
    assert (await other.get(f"/api/v1/groups/{owned['id']}")).status_code == 404

    listing = await other.get("/api/v1/groups")
    assert all(item["id"] != owned["id"] for item in listing.json()["data"])


@pytest.mark.asyncio
async def test_member_cannot_edit_another_members_group(member_client, make_user, sign_in):
    owned = await _create_group(member_client, "Protected Group")
    other = await sign_in(await make_user(Role.USER))

    response = await other.patch(
        f"/api/v1/groups/{owned['id']}", json={"name": "Hijacked"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_editor_can_edit_any_group_in_the_organization(member_client, editor_client):
    owned = await _create_group(member_client, "Shared Group")

    response = await editor_client.patch(
        f"/api/v1/groups/{owned['id']}", json={"name": "Edited By Editor"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Edited By Editor"


@pytest.mark.asyncio
async def test_editor_cannot_delete_a_group_they_do_not_own(member_client, editor_client):
    owned = await _create_group(member_client, "Undeletable")

    response = await editor_client.delete(f"/api/v1/groups/{owned['id']}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_admin_can_delete_any_group(member_client, admin_client):
    owned = await _create_group(member_client, "Deletable")
    assert (await admin_client.delete(f"/api/v1/groups/{owned['id']}")).status_code == 200


@pytest.mark.asyncio
async def test_owner_can_delete_their_own_group(member_client):
    owned = await _create_group(member_client, "Mine To Delete")
    assert (await member_client.delete(f"/api/v1/groups/{owned['id']}")).status_code == 200


# ---------------------------------------------------------------------------
# Administration endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_member_cannot_list_users(member_client):
    assert (await member_client.get("/api/v1/admin/users")).status_code == 403


@pytest.mark.asyncio
async def test_editor_cannot_read_the_audit_log(editor_client):
    assert (await editor_client.get("/api/v1/admin/audit-logs")).status_code == 403


@pytest.mark.asyncio
async def test_admin_can_read_the_audit_log(admin_client):
    assert (await admin_client.get("/api/v1/admin/audit-logs")).status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_reach_system_statistics(admin_client):
    """Platform-wide stats are super-admin only."""
    assert (await admin_client.get("/api/v1/admin/system")).status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_reach_system_statistics(make_user, sign_in):
    superadmin = await sign_in(
        await make_user(Role.ADMIN, system_role=Role.SUPER_ADMIN)
    )
    assert (await superadmin.get("/api/v1/admin/system")).status_code == 200


# ---------------------------------------------------------------------------
# Privilege escalation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_cannot_grant_super_admin(admin_client, make_user):
    target = await make_user(Role.USER)
    response = await admin_client.post(
        f"/api/v1/admin/users/{target.id}/role", json={"role": "SUPER_ADMIN"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_change_their_own_role(admin_client):
    response = await admin_client.post(
        f"/api/v1/admin/users/{admin_client.user.id}/role", json={"role": "SUPER_ADMIN"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_modify_another_admin(admin_client, make_user):
    peer = await make_user(Role.ADMIN)
    response = await admin_client.post(
        f"/api/v1/admin/users/{peer.id}/role", json={"role": "USER"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_suspend_themselves(admin_client):
    response = await admin_client.post(
        f"/api/v1/admin/users/{admin_client.user.id}/status", json={"status": "SUSPENDED"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_promote_a_member_to_editor(admin_client, make_user):
    target = await make_user(Role.USER)
    response = await admin_client.post(
        f"/api/v1/admin/users/{target.id}/role", json={"role": "EDITOR"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/groups"),
        ("POST", "/api/v1/groups"),
        ("GET", "/api/v1/analytics/overview"),
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/media"),
        ("GET", "/api/v1/qr/presets"),
    ],
)
@pytest.mark.asyncio
async def test_protected_endpoints_require_authentication(client, method, path):
    response = await client.request(method, path, json={} if method == "POST" else None)
    assert response.status_code == 401
