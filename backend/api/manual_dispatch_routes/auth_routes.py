from collections.abc import Callable
from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import Response
from backend.schemas import (
    LoginOperatorAccountRequest,
    RegisterOperatorAccountRequest,
    ResetOperatorPasswordRequest,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from .common import (
    ALLOW_REGISTRATION_ENV,
    OPERATOR_COOKIE_NAME,
    REGISTRATION_DISABLED_MESSAGE,
    is_env_flag_enabled,
    set_operator_cookie,
    to_http_exception,
)


def create_auth_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    @router.post("/auth/register")
    def register_operator_account(
        request: RegisterOperatorAccountRequest,
        response: Response,
    ):
        service = get_service()
        if not is_env_flag_enabled(ALLOW_REGISTRATION_ENV, default=True):
            raise HTTPException(status_code=403, detail=REGISTRATION_DISABLED_MESSAGE)

        try:
            identity = service.register_operator_account(request)
            set_operator_cookie(service, response, identity)
            return to_dict(identity)
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/auth/login")
    def login_operator_account(
        request: LoginOperatorAccountRequest,
        response: Response,
    ):
        service = get_service()
        try:
            identity = service.login_operator_account(request)
            set_operator_cookie(service, response, identity)
            return to_dict(identity)
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/auth/logout")
    def logout_operator_account(response: Response):
        service = get_service()
        response.delete_cookie(OPERATOR_COOKIE_NAME, path="/")
        return {"logged_out": True}

    @router.post("/auth/reset-password")
    def reset_operator_password(request: ResetOperatorPasswordRequest):
        service = get_service()
        try:
            return to_dict(service.reset_operator_password(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    return router
