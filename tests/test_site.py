import xml.dom.minidom

from floodwatch import site


def test_feed_is_valid_atom_with_newest_issue_first(monkeypatch):
    issues = [
        ("2027-08-02", {"issued": "2027-08-02", "edition": "morning", "issued_at": "2027-08-02T09:25Z",
                        "days": [{"day": "2027-08-02", "level": "LOW"}], "sms": "morning text"}),
        ("2027-08-02-evening", {"issued": "2027-08-02", "edition": "evening", "issued_at": "2027-08-02T20:50Z",
                                "days": [{"day": "2027-08-02", "level": "HIGH"}], "sms": "evening & text"}),
    ]
    monkeypatch.setattr(site, "_outlooks", lambda: sorted(issues, key=lambda x: x[1]["issued_at"], reverse=True))
    feed = site._feed()
    doc = xml.dom.minidom.parseString(feed)
    entries = doc.getElementsByTagName("entry")
    assert len(entries) == 2
    first = entries[0]
    assert first.getElementsByTagName("title")[0].firstChild.data == "2027-08-02 evening: HIGH (act)"
    # The summary is the short message, built from the issue (not a stored copy).
    assert first.getElementsByTagName("summary")[0].firstChild.data.startswith("Lion Eyes flood outlook, 02 Aug pm: Tonight HIGH.")
    assert doc.getElementsByTagName("updated")[0].firstChild.data == "2027-08-02T20:50:00Z"
