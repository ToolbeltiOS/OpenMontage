"""The Cleveland Museum of Art Open Access API.

Keyless, and the only one of the three museum adapters that states its licence
as a field rather than a boolean: `share_license_status` carries "CC0" for the
open-access subset and other values for the rest. It is passed to the licence
filter as-is rather than being read as a flag, so a new value the museum
introduces is refused as UNKNOWN instead of being silently accepted.
"""
from __future__ import annotations

from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://openaccess-api.clevelandart.org/api/artworks/"
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


class ClevelandArt:
    name = "cleveland_art"
    display_name = "Cleveland Museum of Art (Open Access)"
    priority = 23
    supports = {"image": True, "video": False, "no_api_key": True}
    install_instructions = "No API key required."

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        if filters.kind == "video":
            return []
        per_page = max(filters.per_page, 1)
        payload = _get(_SEARCH, {
            "q": query,
            "limit": per_page,
            "skip": (max(filters.page, 1) - 1) * per_page,
            "has_image": 1,
        })

        candidates: list[Candidate] = []
        for art in payload.get("data", []):
            images = art.get("images") or {}
            picked = images.get("web") or images.get("print") or images.get("full") or {}
            url = picked.get("url")
            if not url:
                continue
            creators = art.get("creators") or []
            creator = (creators[0].get("description", "") if creators
                       else "Cleveland Museum of Art")
            candidates.append(Candidate(
                source=self.name,
                source_id=str(art.get("id")),
                source_url=art.get("url", ""),
                download_url=url,
                kind="image",
                creator=creator,
                license=art.get("share_license_status") or "",
                source_tags=" ".join(filter(None, [
                    art.get("title", ""), art.get("creation_date", ""),
                    art.get("technique", ""), art.get("department", ""),
                    art.get("culture") and ", ".join(art.get("culture") or []),
                ])),
                thumbnail_url=(images.get("web") or {}).get("url", ""),
                extra={"title": art.get("title", ""),
                       "date": art.get("creation_date", ""),
                       "department": art.get("department", "")},
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
