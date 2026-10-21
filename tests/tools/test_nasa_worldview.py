"""The satellite-stills adapter, which is shaped unlike the others.

Worldview has no catalogue to search: it renders a patch of the Earth on
demand. So the query is a PLACE, geocoded against Nominatim, and the thing
being tested is the arithmetic between a point and a 16:9 bounding box, plus
the two manners the services ask for — a real User-Agent and one geocode a
second.

Nothing here touches the network; the live run is recorded in the README.
"""
from __future__ import annotations

import pytest

from tools.video.stock_sources import nasa_worldview as wv
from tools.video.stock_sources.base import SearchFilters


class TestTheBoundingBox:
    def test_the_box_is_16_by_9_around_the_point(self):
        url = wv.snapshot_url(0.0, 0.0, 6.0, "L", "2023-07-15", 1920, 1080)
        bbox = url.split("BBOX=")[1].split("&")[0].replace("%2C", ",")
        south, west, north, east = (float(v) for v in bbox.split(","))
        assert east - west == pytest.approx(6.0)
        assert (north - south) / (east - west) == pytest.approx(1080 / 1920, abs=1e-6)

    def test_the_point_is_the_centre(self):
        url = wv.snapshot_url(-27.12, -109.29, 1.5, "L", "2023-07-15")
        bbox = url.split("BBOX=")[1].split("&")[0].replace("%2C", ",")
        south, west, north, east = (float(v) for v in bbox.split(","))
        assert (south + north) / 2 == pytest.approx(-27.12, abs=1e-4)
        assert (west + east) / 2 == pytest.approx(-109.29, abs=1e-4)

    def test_a_smaller_span_is_a_closer_view(self):
        wide = wv.snapshot_url(0, 0, 6.0, "L", "2023-07-15")
        near = wv.snapshot_url(0, 0, 1.5, "L", "2023-07-15")
        width = lambda u: abs(float(u.split("BBOX=")[1].split("&")[0].replace("%2C", ",").split(",")[3])
                              - float(u.split("BBOX=")[1].split("&")[0].replace("%2C", ",").split(",")[1]))
        assert width(near) < width(wide)


class TestSearch:
    def test_a_place_gives_one_candidate_per_view(self, monkeypatch):
        monkeypatch.setattr(wv, "geocode", lambda q: {
            "lat": -27.12, "lon": -109.29, "display_name": "Rano Raraku",
            "osm_id": "123", "geocode_licence": "ODbL"})
        found = wv.NasaWorldview().search("Rano Raraku",
                                          SearchFilters(kind="image", per_page=4, page=1))
        assert len(found) == len(wv._VIEWS)
        assert {c.extra["layer"] for c in found} == {v[0] for v in wv._VIEWS}

    def test_a_place_that_does_not_geocode_gives_nothing(self, monkeypatch):
        monkeypatch.setattr(wv, "geocode", lambda q: None)
        assert wv.NasaWorldview().search("asdfghjkl",
                                         SearchFilters(kind="image", per_page=4, page=1)) == []

    def test_video_is_not_offered(self):
        assert wv.NasaWorldview().search("Aswan",
                                         SearchFilters(kind="video", per_page=4, page=1)) == []

    def test_the_picture_is_public_domain_and_the_geocode_is_not_its_licence(self, monkeypatch):
        """ODbL is a licence on the coordinates, not on the photograph."""
        monkeypatch.setattr(wv, "geocode", lambda q: {
            "lat": 24.0, "lon": 32.9, "display_name": "Aswan", "osm_id": "9",
            "geocode_licence": "Data © OpenStreetMap contributors, ODbL 1.0"})
        found = wv.NasaWorldview().search("Aswan",
                                          SearchFilters(kind="image", per_page=4, page=1))
        assert found, "a public-domain NASA image was filtered out"
        for c in found:
            assert c.extra["licence_code"] == "PD"
            assert "ODbL" in c.extra["geocode_licence"]
            assert "ODbL" not in c.license


class TestManners:
    def test_the_geocoder_is_not_called_faster_than_once_a_second(self, monkeypatch):
        """Nominatim's published limit, which it enforces by blocking."""
        slept: list[float] = []
        monkeypatch.setattr(wv.time, "sleep", lambda s: slept.append(s))
        clock = iter([100.0, 100.0, 100.2, 100.2])
        monkeypatch.setattr(wv.time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(wv, "_get", lambda url, params, timeout=60: _Stub())
        wv._last_geocode = 0.0
        wv.geocode("a")
        wv.geocode("b")
        assert slept and slept[-1] > 0.8, slept

    def test_both_services_are_told_who_is_calling(self):
        assert "OpenMontage" in wv._UA


class _Stub:
    @staticmethod
    def json():
        return [{"lat": "1.0", "lon": "2.0", "display_name": "x",
                 "osm_id": 1, "licence": "ODbL"}]
