"""The e-mail format rules, pinned to shared/email-cases.json (the frontend checks it too)."""

import json
from pathlib import Path

import pytest

from app.services.mail import email_problem

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "email-cases.json").read_text(
        encoding="utf-8"
    )
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["value"][:24] or "<empty>" for c in CASES])
def test_email_problem_matches_the_shared_cases(case: dict) -> None:
    assert email_problem(case["value"]) == case["problem"]


def test_every_problem_key_is_covered() -> None:
    # the client maps these keys to hints: a new key must get a case (and a hint) on both sides
    assert {c["problem"] for c in CASES} == {
        None,
        "whitespace",
        "too_long",
        "at_sign",
        "local_part",
        "domain",
    }
