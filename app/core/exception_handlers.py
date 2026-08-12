from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core import exceptions


def register_exception_handlers(app: FastAPI):

    def return_error_response(message: str, detail: str, status_code: int):
        return JSONResponse(
            content={"message": message, "detail": detail}, status_code=status_code
        )

    @app.exception_handler(exceptions.Riv3rException)
    async def riv3r_exception_handler(request: Request, exc: exceptions.Riv3rException):
        return return_error_response(
            message=exc.message, detail=exc.detail, status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def unregistered_exception_handler(request: Request, exc: Exception):
        return return_error_response(
            message="Something went wrong",
            detail="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        error = exc.errors()[0]
        field = " ".join(map(str, error["loc"][1:])).capitalize()

        return return_error_response(
            message=f"Validation failed on {field}",
            detail=error["msg"],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
