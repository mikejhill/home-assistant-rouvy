from typing import Any, Optional


class RouvyApiError(Exception):
    pass


class AuthenticationError(RouvyApiError):
    pass


class ApiResponseError(RouvyApiError):
    def __init__(
        self, message: str, status_code: int, payload: Optional[Any] = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
