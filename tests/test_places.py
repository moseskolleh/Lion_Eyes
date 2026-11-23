from floodwatch import geocode


def test_vague_names_are_not_geocoded():
    for name in ["Freetown", "Freetown (neighbourhood not named)", "low-lying areas of Freetown",
                 "east and west of Freetown", "behind P.O.W school", "No. 132 Haja Sonnie Drive"]:
        assert geocode.map_query(name) is None, name


def test_queries_drop_details_and_use_osm_spellings():
    assert geocode.map_query("Kissy (Leone Oil facility)") == "Kissy"
    assert geocode.map_query("PWD Junction, Pademba Road") == "PWD Junction"
    assert geocode.map_query("Dwarzack") == "Dworzark"
    assert geocode.map_query("Kolloh Town") == "Kolleh Town"


def _hit(name, category, kind, lat, lon):
    return {"name": name, "category": category, "type": kind, "lat": str(lat), "lon": str(lon), "display_name": name}


def test_an_area_beats_a_street_and_the_main_road_wins():
    # Pieces of one road, tagged differently along its length: the main-road piece is used.
    hits = [_hit("Kissy Road", "highway", "residential", 8.4805, -13.2150),
            _hit("Kissy Road", "highway", "secondary", 8.4857, -13.2196)]
    best = geocode._best_any("Kissy Road", hits)
    assert best["precision"] == "street" and best["osm_type"] == "secondary"
    area = geocode._best_any("Kingtom", [_hit("Kingtom St", "highway", "residential", 8.48, -13.24),
                                         _hit("Kingtom", "place", "suburb", 8.4874, -13.2449)])
    assert area["precision"] == "area"


def test_same_name_streets_far_apart_are_left_off():
    hits = [_hit("Williams Street", "highway", "residential", 8.473, -13.197),
            _hit("Williams Street", "highway", "residential", 8.433, -13.269)]
    assert geocode._best_any("Williams Street", hits) is None


def test_names_must_match_and_lie_in_the_city():
    assert geocode._best_any("Brookfields", [_hit("Brookfields", "amenity", "hospital", 8.297, -13.027)]) is None
    assert geocode._best_any("Thomas Street", [_hit("St Thomas Primary School", "amenity", "school", 8.483, -13.25)]) is None
