import asyncio
from unittest.mock import AsyncMock, MagicMock

from fastapi import Request
from starlette.datastructures import Headers

from app.services.audit import AuditService


def make_request(**state):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": Headers({"user-agent": "test-agent"}).raw,
        "client": ("127.0.0.1", 1234),
        "state": state,
    }
    return Request(scope)


def make_audit():
    db = AsyncMock()
    db_service = MagicMock()
    db_service.store_audit_log = AsyncMock(return_value=[{}])
    audit = AuditService(db)
    audit.db_service = db_service
    return audit


def test_log_persists_expected_payload():
    audit = make_audit()
    audit._resolve_actor = AsyncMock(return_value="user")

    request = make_request(request_id="req-123", start_time=1234.0)
    asyncio.run(
        audit.log(
            request,
            user_id="user-1",
            entity_type="user",
            task_type="login",
        )
    )

    payload = audit.db_service.store_audit_log.call_args.args[0]
    assert payload["user_id"] == "user-1"
    assert payload["actor"] == "user"
    assert payload["entity_type"] == "user"
    assert payload["task_type"] == "login"
    assert payload["ip_address"] == "127.0.0.1"
    assert payload["user_agent"] == "test-agent"
    assert payload["request_id"] == "req-123"
    assert payload["time_taken_ms"] is not None
    assert payload["time_taken_ms"] >= 0


def test_log_without_start_time_has_none_time():
    audit = make_audit()
    audit._resolve_actor = AsyncMock(return_value="user")

    request = make_request(request_id="req-123")
    asyncio.run(
        audit.log(request, user_id="user-1", entity_type="user", task_type="login")
    )

    payload = audit.db_service.store_audit_log.call_args.args[0]
    assert payload["time_taken_ms"] is None


def test_log_swallows_insert_failure():
    audit = make_audit()
    audit.db_service.store_audit_log = AsyncMock(side_effect=Exception("db down"))
    audit._resolve_actor = AsyncMock(return_value="user")

    request = make_request(request_id="req-123", start_time=1234.0)
    asyncio.run(
        audit.log(request, user_id="user-1", entity_type="user", task_type="login")
    )

    audit.db_service.store_audit_log.assert_awaited_once()


def test_log_explicit_actor_skips_resolution():
    audit = make_audit()

    request = make_request(request_id="req-123", start_time=1234.0)
    asyncio.run(
        audit.log(
            request,
            user_id="u1",
            entity_type="organization",
            task_type="organization_onboard",
            actor="admin",
        )
    )

    payload = audit.db_service.store_audit_log.call_args.args[0]
    assert payload["actor"] == "admin"


def test_resolve_actor_resource_user():
    audit = make_audit()
    audit.db_service.get_user_with_id = AsyncMock(
        return_value={"id": "u1", "is_resource": True}
    )

    assert asyncio.run(audit._resolve_actor("u1")) == "user"


def test_resolve_actor_riv3r_org_is_admin():
    audit = make_audit()
    audit.db_service.get_user_with_id = AsyncMock(
        return_value={"id": "u1", "is_resource": False, "org_id": "org-1"}
    )
    audit.db_service.get_organization_by_id = AsyncMock(
        return_value={"id": "org-1", "org_type": "riv3r"}
    )

    assert asyncio.run(audit._resolve_actor("u1")) == "admin"


def test_resolve_actor_client_org_is_user():
    audit = make_audit()
    audit.db_service.get_user_with_id = AsyncMock(
        return_value={"id": "u1", "is_resource": False, "org_id": "org-1"}
    )
    audit.db_service.get_organization_by_id = AsyncMock(
        return_value={"id": "org-1", "org_type": "client"}
    )

    assert asyncio.run(audit._resolve_actor("u1")) == "user"


def test_resolve_actor_without_org_is_user():
    audit = make_audit()
    audit.db_service.get_user_with_id = AsyncMock(
        return_value={"id": "u1", "is_resource": False}
    )

    assert asyncio.run(audit._resolve_actor("u1")) == "user"


def test_resolve_actor_db_failure_falls_back_to_user():
    audit = make_audit()
    audit.db_service.get_user_with_id = AsyncMock(side_effect=Exception("db down"))

    assert asyncio.run(audit._resolve_actor("u1")) == "user"