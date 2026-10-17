class DomainError(Exception):
    """Base class for expected application errors."""

    status_code = 400
    code = "domain_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BusinessRuleError(DomainError):
    status_code = 400
    code = "business_rule_violation"


class AuthenticationError(DomainError):
    status_code = 401
    code = "authentication_required"


class AuthorizationError(DomainError):
    status_code = 403
    code = "forbidden"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class AccountStateError(DomainError):
    status_code = 403
    code = "account_unavailable"
