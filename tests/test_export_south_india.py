import csv
import runpy

import pytest
import requests

import export_south_india as ex


class Resp:
    def __init__(self, payload=None, status=200):
        self.payload, self.status = payload, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError("bad")

    def json(self):
        return self.payload


@pytest.fixture
def sleeps(monkeypatch):
    s = []
    monkeypatch.setattr(ex.time, "sleep", lambda x: s.append(x))
    return s


def test_fetch_state_success(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ex.requests, "post", lambda url, json, timeout: (calls.append((url, json, timeout)), Resp({"table": [{"rcmcno": 1}]}))[1])
    assert ex.fetch_state("KA", "Karnataka") == [{"rcmcno": 1}]
    assert calls == [(ex.API, {"qType": "13", "expName": "", "expState": "KA", "expType": "ALL", "expProduct": "0000"}, 60)]
    assert "Karnataka (KA): 1 exporters" in capsys.readouterr().err


def test_fetch_state_missing_table_is_empty_list(monkeypatch):
    monkeypatch.setattr(ex.requests, "post", lambda *a, **k: Resp({}))
    assert ex.fetch_state("KA", "Karnataka") == []


def test_fetch_state_retries_then_succeeds(monkeypatch, sleeps, capsys):
    seq = iter([requests.ConnectionError("a"), Resp(status=500), Resp({"table": [{"rcmcno": 9}]})])

    def post(*a, **k):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr(ex.requests, "post", post)
    assert ex.fetch_state("TN", "Tamil Nadu") == [{"rcmcno": 9}]
    assert sleeps == [2, 2]
    err = capsys.readouterr().err
    assert "attempt 1 failed for Tamil Nadu: a" in err and "attempt 2 failed" in err and "giving up" not in err


def test_fetch_state_gives_up_after_three_attempts(monkeypatch, sleeps, capsys):
    n = []

    def post(*a, **k):
        n.append(1)
        raise requests.Timeout("t")

    monkeypatch.setattr(ex.requests, "post", post)
    assert ex.fetch_state("KE", "Kerala") == [] and len(n) == 3 and sleeps == [2, 2, 2]
    assert "giving up on Kerala" in capsys.readouterr().err
    n.clear()
    assert ex.fetch_state("KE", "Kerala", retries=1) == [] and len(n) == 1


def test_main_dedupes_by_rcmc_and_writes_columns(monkeypatch, tmp_path, capsys):
    data = {
        "AP": [{"rcmcno": "R1", "exporter_name": "A", "extra": "dropped"}, {"rcmcno": "R2", "exporter_name": "B"}],
        "TG": [{"rcmcno": "R1", "exporter_name": "dup"}, {"rcmcno": "R3", "exporter_name": "C, Inc"}],
        "KA": [], "KE": [], "TN": [], "PY": [{"rcmcno": None, "exporter_name": "N1"}, {"rcmcno": None, "exporter_name": "N2"}],
    }
    asked = []
    monkeypatch.setattr(ex, "fetch_state", lambda code, name: (asked.append((code, name)), data[code])[1])
    monkeypatch.chdir(tmp_path)
    ex.main()
    assert [c for c, _ in asked] == ["AP", "TG", "KA", "KE", "TN", "PY"]
    rows = list(csv.DictReader((tmp_path / "south_india_exporters.csv").open(encoding="utf-8")))
    assert [r["exporter_name"] for r in rows] == ["A", "B", "C, Inc", "N1"]       # R1 dup dropped; second None key dropped too
    assert list(rows[0]) == ["rcmcno", "exporter_name", "keyPerson", "address", "city", "state", "pin", "email", "mobile",
                                                      "expType", "expStatus", "qtyinMT", "valueinRsCrore"] and rows[0]["address"] == "" and "extra" not in rows[0]
    err = capsys.readouterr().err
    assert "Total unique exporters: 4" in err and "Written to south_india_exporters.csv" in err


def test_state_list():
    assert [c for c, _ in ex.SOUTH_STATES] == ["AP", "TG", "KA", "KE", "TN", "PY"]


def test_script_entry_point(monkeypatch, tmp_path):
    import requests as rq
    monkeypatch.setattr(rq, "post", lambda *a, **k: Resp({"table": [{"rcmcno": "Z", "exporter_name": "Zed"}]}))
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.chdir(tmp_path)
    import pathlib
    runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "export_south_india.py"), run_name="__main__")
    assert (tmp_path / "south_india_exporters.csv").read_text(encoding="utf-8").count("Zed") == 1
