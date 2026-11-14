"""One error format for the whole API: {"error": {"code", "message", "details"}}."""

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    code = getattr(exc, "default_code", "error")
    if isinstance(data, dict) and set(data) == {"detail"}:
        message, details = str(data["detail"]), None
        code = getattr(data["detail"], "code", code)
    else:
        message, details = "The request is not valid.", data
        code = "invalid"
    return Response(error_body(code, message, details), status=response.status_code, headers=response.headers)
