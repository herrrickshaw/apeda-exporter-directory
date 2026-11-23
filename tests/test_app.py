import pytest
import requests

import app as appmod


class Resp:
    def __init__(self, payload=None, status=200, bad_json=False):
        self.payload, self.status, self.bad_json = payload, status, bad_json

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def fresh_cache():
    appmod._cache.update(states=None, products=None)
    yield
    appmod._cache.update(states=None, products=None)


@pytest.fixture
def client():
    appmod.app.testing = True
    return appmod.app.test_client()


@pytest.fixture
def posts(monkeypatch):
    calls = []
    behaviour = {}

    def post(url, json, timeout):
        calls.append((url, json, timeout))
        for suffix, v in behaviour.items():
            if url.endswith(suffix):
                if isinstance(v, Exception):
                    raise v
                return v
        raise AssertionError(url)

    monkeypatch.setattr(appmod.requests, "post", post)
    post.calls, post.behaviour = calls, behaviour
    return post


# ---------------- states / products ----------------
def test_get_states_fetches_once_and_caches(posts):
    posts.behaviour["ExporterDirectory_state"] = Resp({"table": [{"code": "KA"}]})
    assert appmod.get_states() == [{"code": "KA"}]
    assert appmod.get_states() == [{"code": "KA"}]
    assert len(posts.calls) == 1
    assert posts.calls[0] == (appmod.API_BASE + "/ExporterDirectory_state", {"qType": "7"}, 30)


def test_get_products_payload_and_missing_table(posts):
    posts.behaviour["ExporterDirectory_product"] = Resp({})
    assert appmod.get_products() == []
    assert posts.calls[0] == (appmod.API_BASE + "/ExporterDirectory_product", {"qType": "1"}, 30)


@pytest.mark.parametrize("exc", [requests.ConnectionError("down"), requests.Timeout("slow"), requests.HTTPError("500")])
def test_failures_are_cached_as_empty(posts, exc):
    posts.behaviour["ExporterDirectory_state"] = Resp(status=500) if isinstance(exc, requests.HTTPError) else exc
    assert appmod.get_states() == []
    assert appmod._cache["states"] == []                  # a failure is remembered: no retry storm
    appmod.get_states()
    assert len(posts.calls) == 1


def test_http_error_status_is_swallowed(posts):
    posts.behaviour["ExporterDirectory_product"] = Resp(status=503)
    assert appmod.get_products() == []


def test_non_request_exceptions_propagate(posts):
    posts.behaviour["ExporterDirectory_state"] = ValueError("bug")
    with pytest.raises(ValueError):
        appmod.get_states()


# ---------------- index ----------------
def test_index_renders_with_lookups(client, posts):
    posts.behaviour["ExporterDirectory_state"] = Resp({"table": [{"code": "KA", "name": "Karnataka"}]})
    posts.behaviour["ExporterDirectory_product"] = Resp({"table": [{"productID": "0801", "productName": "Cashew"}]})
    r = client.get("/")
    html = r.data.decode()
    assert r.status_code == 200
    assert '<option value="KA">Karnataka</option>' in html and '<option value="0801">Cashew</option>' in html
    assert '<option value="2">Manufacturer</option>' in html


def test_index_survives_backend_down(client, posts):
    posts.behaviour["ExporterDirectory_state"] = requests.ConnectionError("x")
    posts.behaviour["ExporterDirectory_product"] = requests.ConnectionError("x")
    assert client.get("/").status_code == 200


def test_exporter_types_constant():
    assert [t["code"] for t in appmod.EXPORTER_TYPES] == ["ALL", "2", "1", "4"]


# ---------------- /api/search ----------------
def test_search_requires_state(client, posts):
    for qs in ("", "?state=", "?state=%20%20"):
        r = client.get("/api/search" + qs)
        assert r.status_code == 400 and "requires a state" in r.get_json()["error"]
    assert posts.calls == []


def test_search_builds_payload_with_defaults(client, posts):
    posts.behaviour["ExporterDirectory_AllResult"] = Resp({"table": [{"city": "A"}, {"city": "B"}]})
    r = client.get("/api/search?state=KA")
    assert r.get_json() == {"count": 2, "results": [{"city": "A"}, {"city": "B"}]}
    url, payload, timeout = posts.calls[0]
    assert url.endswith("/ExporterDirectory_AllResult") and timeout == 30
    assert payload == {"qType": "13", "expName": "", "expState": "KA", "expType": "ALL", "expProduct": "0000"}


def test_search_passes_filters_stripped(client, posts):
    posts.behaviour["ExporterDirectory_AllResult"] = Resp({"table": []})
    client.get("/api/search?state=%20TN%20&product=0801&type=2&name=%20Acme%20")
    assert posts.calls[0][1] == {"qType": "13", "expName": "Acme", "expState": "TN", "expType": "2", "expProduct": "0801"}


def test_search_empty_product_and_type_fall_back_to_defaults(client, posts):
    posts.behaviour["ExporterDirectory_AllResult"] = Resp({"table": []})
    client.get("/api/search?state=KA&product=&type=")
    p = posts.calls[0][1]
    assert p["expProduct"] == "0000" and p["expType"] == "ALL"          # blank behaves like missing


def test_district_filter_matches_city_or_address_case_insensitively(client, posts):
    rows = [{"city": "Mysuru", "address": "x"}, {"city": None, "address": "12 MYSURU Road"},
            {"city": "Hassan", "address": None}, {"city": "Hassan"}]
    posts.behaviour["ExporterDirectory_AllResult"] = Resp({"table": rows})
    r = client.get("/api/search?state=KA&district=%20MYSURU%20")
    assert r.get_json()["count"] == 2
    assert [x.get("city") for x in r.get_json()["results"]] == ["Mysuru", None]


def test_missing_table_gives_zero_results(client, posts):
    posts.behaviour["ExporterDirectory_AllResult"] = Resp({})
    assert client.get("/api/search?state=KA").get_json() == {"count": 0, "results": []}


def test_backend_failure_is_502_with_reason(client, posts):
    posts.behaviour["ExporterDirectory_AllResult"] = requests.ConnectionError("dns")
    r = client.get("/api/search?state=KA")
    assert r.status_code == 502 and r.get_json()["error"] == "APEDA's live directory could not be reached: dns"
    posts.behaviour["ExporterDirectory_AllResult"] = Resp(status=500)
    assert client.get("/api/search?state=KA").status_code == 502
