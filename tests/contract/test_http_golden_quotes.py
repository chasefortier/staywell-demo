import pytest

from contract_support import CASES, QUOTES_PATH, assert_wire_shape


def test_contract_replays_all_frozen_cases():
    assert len(CASES) == 129
    assert len({case["id"] for case in CASES}) == 129


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_frozen_quote_over_http(client, case):
    response = client.post(QUOTES_PATH, json=case["request"])

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body == case["expected"]
    assert_wire_shape(body)
