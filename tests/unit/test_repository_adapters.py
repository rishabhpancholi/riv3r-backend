from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.supabase import (
    SupabaseAuditLogRepository,
    SupabaseMembershipRepository,
    SupabaseOnboardingRepository,
    SupabaseOrganizationRepository,
    SupabaseRefreshTokenRepository,
    SupabaseResourceRepository,
    SupabaseUserRepository,
)


def database(*responses):
    db = MagicMock()
    query = MagicMock()
    db.table.return_value = query
    for method in ("select", "eq", "insert", "update"):
        getattr(query, method).return_value = query
    query.execute = AsyncMock(
        side_effect=[SimpleNamespace(data=rows) for rows in responses]
    )
    return db, query


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
