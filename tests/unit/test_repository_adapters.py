from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.supabase import (
    SupabaseAuditLogRepository,
    SupabaseMembershipRepository,
    SupabaseOnboardingRepository,
    SupabaseOrganizationRepository,
    SupabasePermissionRepository,
    SupabaseProjectRepository,
    SupabaseRefreshTokenRepository,
    SupabaseResourceRepository,
    SupabaseUserRepository,
)


def database(*responses):
    db = MagicMock()
    query = MagicMock()
    db.table.return_value = query
    for method in ("select", "eq", "insert", "update", "is_", "order"):
        getattr(query, method).return_value = query
    query.execute = AsyncMock(
        side_effect=[SimpleNamespace(data=rows) for rows in responses]
    )
    return db, query


@pytest.mark.asyncio
async def test_list_organization_users_selects_only_public_active_org_users():
    rows = [{"id": "user-a", "name": "Alex"}]
    db, query = database(rows)

    result = await SupabaseUserRepository(db).list_organization_users("org-a")

    assert result == rows
    query.select.assert_called_once_with(
        "id,name,email,phone_number,verification_status,org_id,"
        "created_at,updated_at"
    )
    assert [call.args for call in query.eq.call_args_list] == [
        ("org_id", "org-a"),
        ("is_resource", False),
    ]
    query.is_.assert_called_once_with("deleted_at", "null")
    assert [call.args for call in query.order.call_args_list] == [
        ("name",),
        ("id",),
    ]


@pytest.mark.asyncio
async def test_ownership_filters_both_ids_and_owner_flag():
    db, query = database([{"is_owner": True}])
    assert await SupabaseMembershipRepository(db).check_org_ownership("org-a", "user-a")
    db.table.assert_called_once_with("organization_members")
    assert [call.args for call in query.eq.call_args_list] == [
        ("organization_id", "org-a"),
        ("user_id", "user-a"),
        ("is_owner", True),
    ]


@pytest.mark.asyncio
async def test_resource_update_filters_user_id():
    db, query = database([{"title": "Updated"}])
    result = await SupabaseResourceRepository(db).update_by_user_id(
        "user-a", {"title": "Updated"}
    )
    query.eq.assert_called_once_with("user_id", "user-a")
    query.update.assert_called_once_with({"title": "Updated"})
    assert result == {"title": "Updated"}


@pytest.mark.asyncio
async def test_project_insert_returns_created_record():
    project = {"title": "New project", "org_id": "org-a"}
    db, query = database([{"id": "project-a", **project}])

    result = await SupabaseProjectRepository(db).store_project(project)

    db.table.assert_called_once_with("projects")
    query.insert.assert_called_once_with(project)
    assert result == {"id": "project-a", **project}


@pytest.mark.asyncio
async def test_client_publish_is_atomic_and_tenant_scoped():
    published = {"id": "project-a", "status": "published"}
    db, query = database([published])

    result = await SupabaseProjectRepository(db).publish_draft(
        "project-a",
        "2026-09-29T12:00:00+00:00",
        embedding=[0.1] * 1024,
        embedding_model="voyage-4",
        embedded_at="2026-09-29T12:00:00+00:00",
        organization_id="org-a",
    )

    assert result == published
    assert [call.args for call in query.eq.call_args_list] == [
        ("id", "project-a"),
        ("status", "draft"),
        ("org_id", "org-a"),
    ]
    query.is_.assert_called_once_with("deleted_at", "null")
    query.update.assert_called_once_with(
        {
            "status": "published",
            "published_at": "2026-09-29T12:00:00+00:00",
            "project_embeddings": [0.1] * 1024,
            "embedding_model": "voyage-4",
            "embedded_at": "2026-09-29T12:00:00+00:00",
        }
    )


@pytest.mark.asyncio
async def test_cross_tenant_publish_omits_organization_filter():
    db, query = database([{"id": "project-a", "status": "published"}])

    await SupabaseProjectRepository(db).publish_draft(
        "project-a",
        "2026-09-29T12:00:00+00:00",
        embedding=None,
        embedding_model=None,
        embedded_at=None,
        organization_id=None,
    )

    query.update.assert_called_once_with(
        {
            "status": "published",
            "published_at": "2026-09-29T12:00:00+00:00",
            "project_embeddings": None,
            "embedding_model": None,
            "embedded_at": None,
        }
    )
    assert [call.args for call in query.eq.call_args_list] == [
        ("id", "project-a"),
        ("status", "draft"),
    ]


@pytest.mark.asyncio
async def test_membership_check_filters_organization_and_user():
    db, query = database([{"organization_id": "org-a"}])

    assert await SupabaseMembershipRepository(db).check_org_membership(
        "org-a", "user-a"
    )
    assert [call.args for call in query.eq.call_args_list] == [
        ("organization_id", "org-a"),
        ("user_id", "user-a"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter,method",
    [
        (SupabaseUserRepository, "get_user_with_id"),
        (SupabaseUserRepository, "get_user_with_email"),
        (SupabaseOrganizationRepository, "get_organization_by_id"),
        (SupabaseMembershipRepository, "get_org_membership"),
        (SupabaseResourceRepository, "get_resource_by_user_id"),
    ],
)
async def test_absent_lookup_returns_none(adapter, method):
    db, _ = database([])
    assert await getattr(adapter(db), method)("missing") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rows,expected",
    [
        ([], False),
        (
            [
                {
                    "is_blacklisted": True,
                    "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                }
            ],
            False,
        ),
        (
            [
                {
                    "is_blacklisted": False,
                    "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                }
            ],
            False,
        ),
        (
            [
                {
                    "is_blacklisted": False,
                    "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                }
            ],
            True,
        ),
    ],
)
async def test_refresh_validity(rows, expected):
    db, query = database(rows)
    assert (
        await SupabaseRefreshTokenRepository(db).check_refresh_token_valid("hash")
        is expected
    )
    query.eq.assert_called_once_with("refresh_token", "hash")


@pytest.mark.asyncio
async def test_refresh_reactivation_uses_token_expiry():
    db, query = database([{"id": "existing"}], [])
    expires_at = int((datetime.now(UTC) + timedelta(days=2)).timestamp())
    await SupabaseRefreshTokenRepository(db).store_refresh_token(
        "user-a", "hash", expires_at=expires_at
    )
    update = query.update.call_args.args[0]
    assert update["is_blacklisted"] is False
    assert datetime.fromisoformat(update["expires_at"]).timestamp() == expires_at
    query.insert.assert_not_called()
    assert query.eq.call_args.args == ("refresh_token", "hash")


@pytest.mark.asyncio
async def test_new_refresh_token_stores_exact_token_expiry():
    db, query = database([], [])
    expires_at = 2000000000
    await SupabaseRefreshTokenRepository(db).store_refresh_token(
        "user-a", "hash", expires_at=expires_at
    )
    query.insert.assert_called_once_with(
        {
            "user_id": "user-a",
            "refresh_token": "hash",
            "expires_at": datetime.fromtimestamp(expires_at, UTC).isoformat(),
        }
    )
    query.update.assert_not_called()


@pytest.mark.asyncio
async def test_audit_insert_returns_record_and_propagates_failure():
    payload = {"user_id": "user-a", "task_type": "login"}
    db, query = database([{"id": "log-id", **payload}])
    repo = SupabaseAuditLogRepository(db)
    assert await repo.store_audit_log(payload) == {"id": "log-id", **payload}
    db.table.assert_called_once_with("audit_logs")
    query.insert.assert_called_once_with(payload)
    query.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await repo.store_audit_log(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter,method,table,column",
    [
        (SupabaseUserRepository, "email_exists", "users", "email"),
        (
            SupabaseOrganizationRepository,
            "email_exists",
            "organizations",
            "company_email",
        ),
        (
            SupabaseOrganizationRepository,
            "website_exists",
            "organizations",
            "website_url",
        ),
        (SupabaseResourceRepository, "portfolio_exists", "resources", "portfolio_url"),
        (SupabaseResourceRepository, "linkedin_exists", "resources", "linked_in_url"),
    ],
)
async def test_duplicate_sources_query_their_own_fields(adapter, method, table, column):
    db, query = database([{"id": "found"}], [])
    repo = adapter(db)
    assert await getattr(repo, method)("value") is True
    assert await getattr(repo, method)("absent") is False
    assert db.table.call_args.args == (table,)
    assert query.eq.call_args_list[0].args == (column, "value")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,function",
    [
        ("onboard_organization", "onboard_organization_atomic"),
        ("onboard_resource", "onboard_resource_atomic"),
    ],
)
async def test_onboarding_repository_uses_atomic_rpc(method, function):
    db = MagicMock()
    rpc = MagicMock()
    rpc.execute = AsyncMock(return_value=SimpleNamespace(data={"id": "created"}))
    db.rpc.return_value = rpc
    params = {"p_user_id": "user-a"}

    result = await getattr(SupabaseOnboardingRepository(db), method)(params)

    db.rpc.assert_called_once_with(function, params)
    assert result == {"id": "created"}


@pytest.mark.asyncio
@pytest.mark.parametrize("value,expected", [(True, True), (False, False)])
async def test_permission_repository_uses_effective_permission_rpc(value, expected):
    db = MagicMock()
    rpc = MagicMock()
    rpc.execute = AsyncMock(return_value=SimpleNamespace(data=value))
    db.rpc.return_value = rpc

    result = await SupabasePermissionRepository(db).has_effective_permission(
        "user-a", "projects.create"
    )

    assert result is expected
    db.rpc.assert_called_once_with(
        "user_has_permission",
        {"p_user_id": "user-a", "p_permission_key": "projects.create"},
    )


@pytest.mark.asyncio
async def test_permission_repository_lists_effective_permission_keys():
    db = MagicMock()
    rpc = MagicMock()
    rpc.execute = AsyncMock(
        return_value=SimpleNamespace(
            data=[
                {"permission_key": "projects.create"},
                {"permission_key": "projects.view"},
                {"permission_key": "users.view"},
            ]
        )
    )
    db.rpc.return_value = rpc

    result = await SupabasePermissionRepository(db).list_effective_permissions(
        "user-a"
    )

    assert result == ["projects.create", "projects.view", "users.view"]
    db.rpc.assert_called_once_with("list_user_permissions", {"p_user_id": "user-a"})
