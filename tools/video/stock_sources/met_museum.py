"""The Metropolitan Museum of Art Open Access collection.

Keyless. About half a million objects, of which the open-access subset is
released under CC0 — the Met's own term, not an inference: an object with
``isPublicDomain: true`` carries CC0 on its images, and one without it carries
nothing we may use, whatever the picture looks like.

WHY THE SEARCH URL SAYS v1.1
----------------------------
``/public/collection/v1/search`` was **retired on 2026-10-01** and now answers
410 with a message pointing at ``/public/collection/v1.1/search``, which is
Elastic-backed and paginated with offset and limit rather than returning every
matching ID at once. An adapter written from the older documentation fetches
nothing and looks like an empty catalogue. The object endpoint is still v1.

TWO CALLS PER HIT
-----------------
Search returns object IDs only, so each one needs its own fetch for the image
URL and the rights field. That is the API's shape, not a choice; the per-page
limit keeps it honest.
"""
from __future__ import annotations

from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
_UA = "OpenMontage/1.0 (documentary asset bank; keyless open-access use)"


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


class MetMuseum:
    name = "met_museum"
    display_name = "The Metropolitan Museum of Art (Open Access)"
    priority = 20
    supports = {"image": True, "video": False, "no_api_key": True}
    install_instructions = "No API key required."

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        if filters.kind == "video":
            return []                      # the Met's open access is stills

        found = _get(_SEARCH, {
            "q": query,
            "hasImages": "true",
            "limit": max(filters.per_page, 1),
            "offset": max(filters.page - 1, 0) * max(filters.per_page, 1),
        })
        ids = (found.get("objectIDs") or [])[: max(filters.per_page, 1)]

        candidates: list[Candidate] = []
        for object_id in ids:
            try:
                obj = _get(f"{_OBJECT}/{object_id}")
            except Exception:
                continue                   # one bad object must not kill the page
            image = obj.get("primaryImage") or obj.get("primaryImageSmall")
            if not image:
                continue
            # The Met states CC0 for the open-access subset and nothing for the
            # rest. `rightsAndReproduction` is a free-text note about the
            # OBJECT, not a licence for the image, so it is carried in extra
            # and never used as the licence.
            licence = "CC0 1.0" if obj.get("isPublicDomain") else ""
            candidates.append(Candidate(
                source=self.name,
                source_id=str(object_id),
                source_url=obj.get("objectURL", ""),
                download_url=image,
                kind="image",
                creator=obj.get("artistDisplayName") or "The Metropolitan Museum of Art",
                license=licence,
                source_tags=" ".join(filter(None, [
                    obj.get("title", ""), obj.get("objectDate", ""),
                    obj.get("medium", ""), obj.get("department", ""),
                    obj.get("culture", ""), obj.get("objectName", ""),
                ])),
                thumbnail_url=obj.get("primaryImageSmall", ""),
                extra={
                    "title": obj.get("title", ""),
                    "date": obj.get("objectDate", ""),
                    "department": obj.get("department", ""),
                    "rights_note": obj.get("rightsAndReproduction", ""),
                },
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
