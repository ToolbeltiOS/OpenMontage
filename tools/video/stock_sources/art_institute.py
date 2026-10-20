"""The Art Institute of Chicago's public API.

Keyless. Search returns the fields asked for in one call — no per-object
round trip — and the image lives on a IIIF endpoint whose base URL the API
returns in `config.iiif_url` rather than being hard-coded here, so a change
of CDN does not silently break every download.

Licence: `is_public_domain` is the Art Institute's own CC0 flag. Everything
else is refused; the API also carries works that are in copyright and shows
them, which is exactly the case the licence filter exists for.
"""
from __future__ import annotations

from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://api.artic.edu/api/v1/artworks/search"
_FIELDS = ("id,title,artist_title,is_public_domain,image_id,date_display,"
           "medium_display,department_title,place_of_origin")
_UA = "OpenMontage/1.0 (documentary asset bank; keyless open-access use)"
#: IIIF size. 1686px on the long edge is enough for a 1080p push without
#: pulling the full-resolution master for every candidate.
_IIIF_SIZE = "1686,"


def _get(url: str, params: dict | None = None, timeout: int = 30) -> dict:
    """GET JSON through `requests`, imported lazily inside the call.

    Lazily and through `requests` for the same reason every other adapter
    does: the contract tests stub that module to prove an adapter propagates
    transport errors and returns [] on an empty page. An adapter using urllib
    bypasses the stub and makes real calls during the suite.
    """
    import requests

    response = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": _UA})
    response.raise_for_status()
    return response.json()


class ArtInstituteChicago:
    name = "art_institute"
    display_name = "Art Institute of Chicago"
    priority = 22
    supports = {"image": True, "video": False, "no_api_key": True}
    install_instructions = "No API key required."

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        if filters.kind == "video":
            return []
        payload = _get(_SEARCH, {
            "q": query,
            "limit": max(filters.per_page, 1),
            "page": max(filters.page, 1),
            "fields": _FIELDS,
        })
        iiif = (payload.get("config") or {}).get("iiif_url", "https://www.artic.edu/iiif/2")

        candidates: list[Candidate] = []
        for art in payload.get("data", []):
            image_id = art.get("image_id")
            if not image_id:
                continue
            url = f"{iiif}/{image_id}/full/{_IIIF_SIZE}/0/default.jpg"
            candidates.append(Candidate(
                source=self.name,
                source_id=str(art.get("id")),
                source_url=f"https://www.artic.edu/artworks/{art.get('id')}",
                download_url=url,
                kind="image",
                creator=art.get("artist_title") or "Art Institute of Chicago",
                license="CC0 1.0" if art.get("is_public_domain") else "",
                source_tags=" ".join(filter(None, [
                    art.get("title", ""), art.get("date_display", ""),
                    art.get("medium_display", ""), art.get("department_title", ""),
                    art.get("place_of_origin", ""),
                ])),
                thumbnail_url=f"{iiif}/{image_id}/full/400,/0/default.jpg",
                extra={"title": art.get("title", ""),
                       "date": art.get("date_display", ""),
                       "department": art.get("department_title", "")},
            ))
        return filter_candidates(candidates)

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import requests

        response = requests.get(candidate.download_url, timeout=120,
                                headers={"User-Agent": _UA})
        response.raise_for_status()
        out_path.write_bytes(response.content)
        return out_path
