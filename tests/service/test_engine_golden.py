import pytest

from service_cases import frozen_cases, service_request

from quote_service.pricing import get_quote
from quote_service.serialization import quote_to_dict

CASES = frozen_cases()


def test_fixture_has_all_cases():
    assert len(CASES) == 129
    assert len({case["id"] for case in CASES}) == 129


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_engine_matches_frozen_quote(case):
    actual = quote_to_dict(get_quote(service_request(case["request"])))
    assert actual == case["expected"]
    assert list(actual) == list(case["expected"])
