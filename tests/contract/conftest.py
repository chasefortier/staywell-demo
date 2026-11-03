import httpx
import pytest

from contract_support import BASE_URL


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as http:
        try:
            http.get("/healthz")
        except httpx.TransportError as exc:
            pytest.fail(f"quote service is not reachable at {BASE_URL}; start it with scripts/serve.sh ({exc!r})")
        yield http
