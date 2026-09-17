"""Does the domain of an e-mail address receive mail at all? A DNS question, asked on save.

The format check (services/mail.py) cannot tell `gmail.com` from `gmail.con`; DNS can: the
domain either publishes mail exchangers or it does not exist. The rule follows RFC 5321 §5.1
and RFC 7505, the same way common validators do:

- at least one MX record other than the null MX (`MX 0 .`) — someone receives mail there;
- only the null MX — the domain says it accepts no mail (`example.com` publishes exactly this);
- no MX at all — an A or AAAA record counts as an implicit MX; nothing at all, or no such
  domain (NXDOMAIN) — no mail server.

DNS trouble (timeout, SERVFAIL, no network) is not the rider's fault: the address is accepted
and a warning is logged. Existence of the mailbox itself is never checked — that would take
sending a message, and the mailbox is a stub.
"""

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

import dns.asyncresolver
import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)

NO_MAIL_SERVER = "no_mail_server"  # the `problem` key the client turns into a hint


class Resolver(Protocol):
    async def resolve(self, qname: str, rdtype: str, *, lifetime: float) -> Iterable[Any]: ...


async def _records(resolver: Resolver, domain: str, rdtype: str, lifetime: float) -> list[Any]:
    """The records of one type; an empty list when the name exists but has none."""
    try:
        return list(await resolver.resolve(domain, rdtype, lifetime=lifetime))
    except dns.resolver.NoAnswer:
        return []


async def mail_domain_problem(domain: str, *, resolver: Resolver, lifetime: float) -> str | None:
    """`no_mail_server` when DNS says nobody receives mail at `domain`; None when somebody does
    or DNS could not be asked (then a warning is logged and the address is let through)."""
    try:
        exchangers = await _records(resolver, domain, "MX", lifetime)
        if exchangers:
            has_real_exchanger = any(str(rdata.exchange) != "." for rdata in exchangers)
            return None if has_real_exchanger else NO_MAIL_SERVER
        for rdtype in ("A", "AAAA"):  # RFC 5321: an address record is an implicit MX
            if await _records(resolver, domain, rdtype, lifetime):
                return None
        return NO_MAIL_SERVER
    except dns.resolver.NXDOMAIN:
        return NO_MAIL_SERVER
    except (dns.exception.DNSException, OSError) as exc:
        logger.warning("DNS check of %s skipped, accepting the address: %r", domain, exc)
        return None


@dataclass
class DomainChecker:
    """The app-level check: switched off by EMAIL_DOMAIN_CHECK=false (tests, CI, offline demo)."""

    enabled: bool
    timeout: float
    resolver: Resolver

    async def problem(self, domain: str) -> str | None:
        if not self.enabled:
            return None
        return await mail_domain_problem(domain, resolver=self.resolver, lifetime=self.timeout)


WARM_UP_DOMAIN = "gmail.com"  # any real mail domain; the demo suggests this one anyway


async def warm_up(
    checker: DomainChecker,
    *,
    attempts: int = 30,
    pause: float = 2.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Ask DNS once at startup, retrying until it answers (or `attempts` run out), so the
    rider's first save does not hit the cold path: Docker's embedded DNS may take tens of
    seconds to forward queries after a container start, and every check in that window would
    time out and let a typo through. Never raises."""
    if not checker.enabled:
        return
    for attempt in range(1, attempts + 1):
        try:
            await checker.resolver.resolve(WARM_UP_DOMAIN, "MX", lifetime=checker.timeout)
        except (dns.exception.DNSException, OSError) as exc:
            if attempt == attempts:
                logger.warning("DNS still not answering after %d attempts: %r", attempts, exc)
                return
            await sleep(pause)
        else:
            logger.info("DNS check of e-mail domains ready (attempt %d)", attempt)
            return


@functools.cache
def system_resolver(per_try_timeout: float) -> Resolver:
    """dnspython's async resolver over the system's nameservers (/etc/resolv.conf, or the OS),
    built once per setting. `per_try_timeout` is how long one attempt waits; with half the
    lifetime a lost UDP packet costs one retry, not the whole budget. A host without any DNS
    configuration gets a resolver that always fails, which `mail_domain_problem` treats as DNS
    trouble (address accepted, warning logged)."""
    try:
        resolver = dns.asyncresolver.Resolver()
    except dns.exception.DNSException as exc:
        logger.warning("No DNS configuration, e-mail domains will not be checked: %r", exc)
        return _NoResolver(exc)
    resolver.timeout = per_try_timeout
    return resolver


class _NoResolver:
    def __init__(self, reason: dns.exception.DNSException) -> None:
        self._reason = reason

    async def resolve(self, qname: str, rdtype: str, *, lifetime: float) -> Iterable[Any]:
        raise self._reason
