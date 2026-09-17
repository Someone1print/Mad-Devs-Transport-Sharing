"""The DNS check of an e-mail domain: does anybody receive mail there?

Every test drives `mail_domain_problem` with a fake resolver, so nothing touches the network.
"""

import logging
from dataclasses import dataclass, field

import dns.resolver
import pytest

from app.services.mail_domain import DomainChecker, mail_domain_problem


@dataclass
class Rdata:
    exchange: str = ""


@dataclass
class FakeResolver:
    """Answers per record type: a list of rdata, or an exception to raise."""

    answers: dict[str, object] = field(default_factory=dict)
    queries: list[tuple[str, str, float]] = field(default_factory=list)

    async def resolve(self, qname: str, rdtype: str, *, lifetime: float) -> list[object]:
        self.queries.append((qname, rdtype, lifetime))
        answer = self.answers.get(rdtype, dns.resolver.NoAnswer())
        if isinstance(answer, BaseException):
            raise answer
        return list(answer)


async def test_a_domain_with_mx_records_is_fine() -> None:
    resolver = FakeResolver({"MX": [Rdata("alt1.gmail-smtp-in.l.google.com.")]})

    assert await mail_domain_problem("gmail.com", resolver=resolver, lifetime=2.0) is None
    assert resolver.queries == [("gmail.com", "MX", 2.0)]


async def test_a_domain_that_does_not_exist_has_no_mail_server() -> None:
    resolver = FakeResolver({"MX": dns.resolver.NXDOMAIN()})

    assert await mail_domain_problem("gmail.con", resolver=resolver, lifetime=2.0) == (
        "no_mail_server"
    )


async def test_a_null_mx_means_the_domain_refuses_mail() -> None:
    # RFC 7505: "MX 0 ." says the domain accepts no mail (example.com publishes exactly this)
    resolver = FakeResolver({"MX": [Rdata(".")]})

    assert await mail_domain_problem("example.com", resolver=resolver, lifetime=2.0) == (
        "no_mail_server"
    )


async def test_without_mx_an_address_record_counts_as_an_implicit_mx() -> None:
    # RFC 5321 §5.1: no MX but an A/AAAA record — mail goes to that host
    resolver = FakeResolver({"MX": dns.resolver.NoAnswer(), "A": [Rdata()]})

    assert await mail_domain_problem("mail.example.org", resolver=resolver, lifetime=2.0) is None
    assert [q[1] for q in resolver.queries] == ["MX", "A"]


async def test_without_any_record_there_is_no_mail_server() -> None:
    resolver = FakeResolver({"MX": dns.resolver.NoAnswer()})  # A and AAAA: NoAnswer too

    assert await mail_domain_problem("nomail.example.org", resolver=resolver, lifetime=2.0) == (
        "no_mail_server"
    )
    assert [q[1] for q in resolver.queries] == ["MX", "A", "AAAA"]


@pytest.mark.parametrize(
    "failure",
    [dns.resolver.LifetimeTimeout(), dns.resolver.NoNameservers(), OSError("network down")],
    ids=["timeout", "servfail", "os-error"],
)
async def test_dns_trouble_lets_the_address_through_with_a_warning(
    failure: BaseException, caplog: pytest.LogCaptureFixture
) -> None:
    resolver = FakeResolver({"MX": failure})

    with caplog.at_level(logging.WARNING, logger="app.services.mail_domain"):
        problem = await mail_domain_problem("gmail.com", resolver=resolver, lifetime=1.5)

    assert problem is None
    assert any("gmail.com" in record.message for record in caplog.records)


async def test_a_disabled_checker_never_asks_dns() -> None:
    resolver = FakeResolver({"MX": dns.resolver.NXDOMAIN()})
    checker = DomainChecker(enabled=False, timeout=2.0, resolver=resolver)

    assert await checker.problem("gmail.con") is None
    assert resolver.queries == []


async def test_an_enabled_checker_uses_its_timeout() -> None:
    resolver = FakeResolver({"MX": dns.resolver.NXDOMAIN()})
    checker = DomainChecker(enabled=True, timeout=1.0, resolver=resolver)

    assert await checker.problem("gmail.con") == "no_mail_server"
    assert resolver.queries == [("gmail.con", "MX", 1.0)]
