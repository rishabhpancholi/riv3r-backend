"""Interface-constrained test dependencies; no storage clients required."""

from types import SimpleNamespace
from unittest.mock import create_autospec

from app.repositories import contracts
from app.services.duplicates import DuplicateChecker


def repository_mocks():
    repositories = SimpleNamespace(
        users=create_autospec(contracts.UserRepository, instance=True, spec_set=True),
        organizations=create_autospec(
            contracts.OrganizationRepository, instance=True, spec_set=True
        ),
        memberships=create_autospec(
            contracts.MembershipRepository, instance=True, spec_set=True
        ),
        resources=create_autospec(
            contracts.ResourceRepository, instance=True, spec_set=True
        ),
        refresh_tokens=create_autospec(
            contracts.RefreshTokenRepository, instance=True, spec_set=True
        ),
        onboarding=create_autospec(
            contracts.OnboardingRepository, instance=True, spec_set=True
        ),
        audit_logs=create_autospec(
            contracts.AuditLogRepository, instance=True, spec_set=True
        ),
        revocations=create_autospec(
            contracts.AccessTokenRevocationStore, instance=True, spec_set=True
        ),
        duplicates=create_autospec(DuplicateChecker, instance=True, spec_set=True),
    )
    repositories.users.get_user_with_id.return_value = None
    repositories.users.get_user_with_email.return_value = None
    repositories.organizations.get_organization_by_id.return_value = None
    repositories.memberships.get_org_membership.return_value = None
    repositories.resources.get_resource_by_user_id.return_value = None
    repositories.revocations.is_revoked.return_value = False
    return repositories


class MemoryRevocations:
    def __init__(self):
        self.tokens = set()

    async def revoke(self, raw_token: str, *, expires_at: int) -> None:
        self.tokens.add(raw_token)

    async def is_revoked(self, raw_token: str) -> bool:
        return raw_token in self.tokens
