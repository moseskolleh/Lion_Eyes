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


def test_warning_colours_follow_the_international_code():
    # Green = no warning, yellow = be aware (Watch), orange = be prepared (Act); red kept for a flood warning.
    css = site.CSS
    for token, colour in [("--lvl-low", "#00a651"), ("--lvl-elev", "#ffdd00"), ("--lvl-high", "#ff8c00"),
                          ("--lvl-red", "#e3000f")]:
        assert f"{token}:{colour}" in css
    assert "#7CFC00;--lvl" not in css  # the old lawn green is no longer a level colour


def test_layers_panel_groups_and_search_box():
    panel = site._layers_panel()
    for group in ("Today's outlook", "Flood hazard", "Landslide hazard", "People and places", "Base map"):
        assert f"<summary>{group}</summary>" in panel
    for layer in ("zones", "low", "streams", "floods", "steep", "buildings", "roads", "facilities", "worship", "pop", "relief"):
        assert f'data-layer="{layer}"' in panel
    assert 'id="q" type="search"' in panel and 'role="combobox"' in panel
    assert panel.count('name="basemap"') == len(site.BASEMAPS)


def test_past_flood_points_merge_names_and_list_events():
    gj = site._places_geojson()
    feats = gj["features"]
    assert feats
    for f in feats:
        p = f["properties"]
        assert p["events"] == len(p["list"]) > 0
        assert p["precision"] in {"area", "street", "landmark"}
        assert all(e["id"].startswith("FT-") for e in p["list"])
    # Two reported names that geocode to one spot become one marker.
    names = {f["properties"]["place"]: f["properties"]["aka"] for f in feats}
    assert any(aka for aka in names.values())


def test_flood_history_cards_have_anchors_and_map_links():
    page = site._floods_page()
    assert 'id="FT-20130808"' in page
    assert 'href="index.html#place=' in page
    assert 'class="yearnav"' in page


def test_flood_history_names_the_month_with_most_floods():
    from floodwatch import events

    cat = events.load_catalogue()
    by_month = cat.groupby(cat["date"].dt.month).size()
    top = by_month.idxmax()
    name = ["January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December"][top - 1]
    assert f"in {name}, the worst month" in site._floods_page()


def test_map_colour_ramps_match_the_layers_and_the_key():
    """The population ramp and its class edges are written in three places; they must agree."""
    from pathlib import Path

    from floodwatch import config, maplayers

    assert site.POP_BREAKS == [lo for lo, _ in maplayers.POP_STEPS]
    assert len(site.POP_RAMP) == len(site.POP_BREAKS)
    js = (config.REPO_ROOT / "site_assets" / "map.js").read_text()
    assert "const POP = [" + ", ".join(f"'{c}'" for c in site.POP_RAMP) + "];" in js
    panel = site._layers_panel()
    assert "120-200" in panel and "200+" in panel
    assert 'id="mapkey"' in panel
    assert maplayers.CORE_HAND_M < 3.0  # the "floods first" band sits inside the flood-prone ground


def test_how_it_works_reading_lists_have_no_thumbnails():
    page = site._about_page()
    assert 'class="readmore"' in page
    start = page.index('class="readmore"')
    assert "<img" not in page[start:page.index("Get the outlook")]
