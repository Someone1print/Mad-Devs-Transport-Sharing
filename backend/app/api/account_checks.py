"""The e-mail checks shared by registration and the account: format, then the mail domain."""

from fastapi import HTTPException, status

from app.api.deps import api_error
from app.core.config import settings
from app.services.mail import email_problem
from app.services.mail_domain import DomainChecker, system_resolver


def get_domain_checker() -> DomainChecker:
    """The DNS check of an address domain, configured from the settings at request time (so a
    test can switch it off); tests of the check itself override this with a fake resolver."""
    lifetime = settings.email_domain_check_timeout_seconds
    return DomainChecker(
        enabled=settings.email_domain_check,
        timeout=lifetime,
        resolver=system_resolver(per_try_timeout=lifetime / 2),
    )


def invalid_email(problem: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={**api_error("invalid_email", f"E-mail problem: {problem}"), "problem": problem},
    )


async def address_problem(email: str, checker: DomainChecker) -> None:
    """Raise 422 `invalid_email` naming the failed rule: `empty`, a format key, or
    `no_mail_server` from DNS. The format is checked first, so DNS is never asked about junk."""
    stripped = email.strip()
    if not stripped:
        raise invalid_email("empty")
    problem = email_problem(stripped) or await checker.problem(stripped.rsplit("@", 1)[1])
    if problem is not None:
        raise invalid_email(problem)
