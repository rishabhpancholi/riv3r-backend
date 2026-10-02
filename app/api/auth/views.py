from app.api.onboarding.views import User


class CurrentUser(User):
    permissions: list[str]
