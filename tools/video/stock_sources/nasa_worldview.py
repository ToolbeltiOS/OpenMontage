"""Satellite stills of a named place, from NASA Worldview.

WHAT THIS IS, AND WHY IT IS SHAPED DIFFERENTLY
-----------------------------------------------
Every other adapter here searches a catalogue. This one does not: Worldview
has no catalogue to search. It is a renderer — give it a bounding box, a date
and a layer and it draws you that patch of the Earth on that day. The picture
does not exist until it is asked for.

So the query is a PLACE, not a subject. "Rano Raraku" is geocoded against
OpenStreetMap's Nominatim, which is keyless, and the resulting point becomes a
box at the requested span. "Quarry" returns nothing useful and is supposed to:
this is the source for "the site, from above", which a documentary about
places wants often and an archive rarely has.

TWO SERVICES, BOTH KEYLESS, BOTH WITH MANNERS
---------------------------------------------
Nominatim asks for a real User-Agent and no more than one request a second,
and will block a client that ignores either. The snapshot API is NASA's and
has no stated rate limit, but it renders on demand, so a wide box at high
resolution is a slow request for them and for us.

LICENSING
---------
NASA's imagery is public domain under its media usage policy and that is what
the candidate carries. The GEOCODE is ODbL from OpenStreetMap, which is a
licence on the coordinates and not on the picture — it is recorded in `extra`
for attribution and is deliberately not the candidate's licence, because the
thing being licensed is the image.

    MODIS at 250m resolves a city, not a stone. For a site the useful layers
    are the Landsat and Sentinel-2 ones, and even those stop at 10m — this is
    for showing WHERE a thing is, not what it looks like.
"""
from __future__ import annotations

import time
from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_GEOCODE = "https://nominatim.openstreetmap.org/search"
_SNAPSHOT = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"
_UA = "OpenMontage/1.0 (documentary asset bank; contact via repository)"

#: NASA's own wording. The licence filter reads it as public domain.
_LICENCE = "Public domain (NASA Earth Observing System Data and Information System)"

#: Layers worth asking for, widest first. Each is a (layer, span in degrees,
#: label) — the span is how much of the Earth the frame covers, which is the
#: only zoom control the snapshot API has.
_VIEWS = [
    ("MODIS_Terra_CorrectedReflectance_TrueColor", 6.0, "regional"),
    ("VIIRS_SNPP_CorrectedReflectance_TrueColor", 1.5, "local"),
]

#: Nominatim's published limit is one request a second, and it enforces it.
_GEOCODE_INTERVAL_S = 1.1
_last_geocode = 0.0


def _get(url: str, params: dict, timeout: int = 60):
    import requests

    response = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": _UA})
    response.raise_for_status()
    return response


def geocode(place: str) -> dict | None:
    """The place, as a point, from OpenStreetMap. Keyless and rate-limited."""
    global _last_geocode

    wait = _GEOCODE_INTERVAL_S - (time.monotonic() - _last_geocode)
    if wait > 0:
        time.sleep(wait)
    _last_geocode = time.monotonic()

    found = _get(_GEOCODE, {"q": place, "format": "json", "limit": 1}).json()
    if not found:
        return None
    first = found[0]
    return {
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
        "display_name": first.get("display_name", place),
        "osm_id": str(first.get("osm_id", "")),
        "geocode_licence": first.get("licence", ""),
    }


def snapshot_url(lat: float, lon: float, span: float, layer: str,
                 date: str, width: int = 1920, height: int = 1080) -> str:
    """The URL that renders this patch of Earth. 16:9, because the film is."""
    half_x = span / 2
    half_y = half_x * height / width
    bbox = f"{lat - half_y:.5f},{lon - half_x:.5f},{lat + half_y:.5f},{lon + half_x:.5f}"
    from urllib.parse import urlencode

    return f"{_SNAPSHOT}?" + urlencode({
        "REQUEST": "GetSnapshot",
        "LAYERS": layer,
        "CRS": "EPSG:4326",
        "TIME": date,
        "BBOX": bbox,
        "FORMAT": "image/jpeg",
        "WIDTH": width,
        "HEIGHT": height,
    })


class NasaWorldview:
    name = "nasa_worldview"
    display_name = "NASA Worldview (satellite snapshots)"
    priority = 30
    supports = {"image": True, "video": False, "no_api_key": True}
    install_instructions = "No API key required."

    #: Cloud cover is the risk; a summer date in the northern hemisphere is
    #: the least bad default that does not need a cloud-mask round trip.
    default_date = "2023-07-15"

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        if filters.kind == "video":
            return []                      # snapshots are stills
        place = geocode(query)
        if place is None:
            return []

        date = getattr(filters, "date", None) or self.default_date
        candidates: list[Candidate] = []
        for layer, span, label in _VIEWS:
            url = snapshot_url(place["lat"], place["lon"], span, layer, date)
            candidates.append(Candidate(
                source=self.name,
                source_id=f"{place['osm_id'] or query}:{label}:{date}",
                source_url="https://worldview.earthdata.nasa.gov/",
                download_url=url,
                kind="image",
                creator="NASA EOSDIS Worldview",
                license=_LICENCE,
                source_tags=f"{place['display_name']} satellite {label} {layer}",
                thumbnail_url=url,
                extra={
                    "place": place["display_name"],
                    "lat": place["lat"],
                    "lon": place["lon"],
                    "span_degrees": span,
                    "layer": layer,
                    "date": date,
                    # the coordinates are ODbL; the picture is not
                    "geocode_licence": place["geocode_licence"],
                    "geocode_source": "OpenStreetMap Nominatim",
                },
            ))
        return filter_candidates(candidates)

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        response = _get(candidate.download_url, {}, timeout=180)
        out_path.write_bytes(response.content)
        return out_path
