from typing import Literal

from app.api.onboarding.views import User


class CurrentUser(User):
    permissions: list[str]
    org_type: Literal["client", "agency", "riv3r"] | None
