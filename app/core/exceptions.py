from fastapi import status
class Riv3rException(Exception):
    def __init__(
        self,
        message: str = "Something went wrong",
        detail: str = "",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        super().__init__()

        self.message = message
        self.detail = detail
        self.status_code = status_code

    def __str__(self):
        return self.message


class DuplicateError(Riv3rException):
    def __init__(self, entity: str, value: str):
        super().__init__(
            message=f"{entity.capitalize()} with {value} already exists",
            detail=f"Please make sure the {entity} does not already exist",
            status_code=status.HTTP_409_CONFLICT,
        )

class AuthorizationError(Riv3rException):
    def __init__(self, message: str = "Unauthorized", detail: str = ""):
        super().__init__(
            message=message,
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

class PermissionError(Riv3rException):
    def __init__(self, message: str = "Forbidden", detail: str = ""):
        super().__init__(
            message=message,
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
        )

class RateLimitError(Riv3rException):
    def __init__(self):
        super().__init__(
            message="Too many login attempts. Please try again later.",
            detail="Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

class NotFoundError(Riv3rException):
    def __init__(self, entity: str):
        super().__init__(
            message=f"{entity.capitalize()} not found",
            detail=f"Please make sure the {entity} exists",
            status_code=status.HTTP_404_NOT_FOUND,
        )
