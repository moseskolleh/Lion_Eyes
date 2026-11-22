import json

import pytest

from floodwatch import events

ROW = {
    "date": "2015-09-16",
    "date_confidence": "exact",
    "time_of_day": None,
    "end_date": None,
    "type": "flash_flood",
    "locations": ["Kroo Bay", "Culvert"],
    "deaths": 10,
    "affected": 12000,
    "houses_damaged": None,
    "rain_note": None,
    "summary": "s",
    "evidence": "e",
    "sources": ["https://example.org/a"],
}


def test_coastal_detection():
    assert events.is_coastal(["Kroo Bay"])
    assert not events.is_coastal(["Regent"])


def test_build_merges_same_day(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "EVENTS_DIR", tmp_path)
    monkeypatch.setattr(events, "CATALOGUE_CSV", tmp_path / "c.csv")
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(json.dumps(ROW) + "\n")
    b.write_text(json.dumps({**ROW, "locations": ["Lumley"], "sources": ["https://example.org/b"], "deaths": 12}) + "\n")
    df = events.build_catalogue([str(a), str(b)])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["locations"] == ["Kroo Bay", "Culvert", "Lumley"]
    assert row["deaths"] == 12
    assert row["coastal"]
    back = events.load_catalogue(tmp_path / "c.csv")
    assert back.iloc[0]["sources"] == ["https://example.org/a", "https://example.org/b"]


def test_rejects_unsourced(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({**ROW, "sources": []}) + "\n")
    with pytest.raises(ValueError):
        events.build_catalogue([str(p)])
