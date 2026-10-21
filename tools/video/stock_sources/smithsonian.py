"""The Smithsonian Open Access collection.

Fifteen million records across nineteen museums, of which the open-access
subset is released CC0. Needs a key from api.data.gov, which is free; without
one the API answers 403 and this adapter reports itself unavailable rather
than failing mid-run.

WHAT THE RIGHTS FIELD LOOKS LIKE
--------------------------------
Two places say something about rights and they do not agree in shape.
`content.descriptiveNonRepeating.metadata_usage.access` carries "CC0" for the
open subset, and individual media records carry their own `usage.access`.
The MEDIA record is the one that governs the file being downloaded, so that is
what is passed to the filter; the object-level field is carried in `extra` for
reading and is never used as the licence.

A record with no usable media is skipped rather than returned with an empty
download URL, which is how a candidate ends up in a bank with nothing behind
it.
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://api.si.edu/openaccess/api/v1.0/search"
_UA = "OpenMontage/1.0 (documentary asset bank)"
ENV_KEY = "SMITHSONIAN_API_KEY"


def _get(url: str, params: dict, timeout: int = 60) -> dict:
    import requests

    response = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": _UA})
    response.raise_for_status()
    return response.json()


class Smithsonian:
    name = "smithsonian"
    display_name = "Smithsonian Open Access"
    priority = 21
    supports = {"image": True, "video": False, "no_api_key": False}
    install_instructions = (
        f"Set {ENV_KEY} in .env to enable Smithsonian Open Access "
        "(free key at https://api.data.gov/signup/)."
    )

    def is_available(self) -> bool:
        return bool(os.environ.get(ENV_KEY))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        key = os.environ.get(ENV_KEY)
        if not key or filters.kind == "video":
            return []
        per_page = max(filters.per_page, 1)
        found = _get(_SEARCH, {
            "api_key": key,
            "q": f"{query} AND online_media_type:\"Images\"",
            "rows": per_page,
            "start": (max(filters.page, 1) - 1) * per_page,
        })

        candidates: list[Candidate] = []
        for row in ((found.get("response") or {}).get("rows") or []):
            content = row.get("content") or {}
            descriptive = content.get("descriptiveNonRepeating") or {}
            media = ((descriptive.get("online_media") or {}).get("media") or [])
            if not media:
                continue                   # nothing to download
            first = media[0]
            url = first.get("content") or first.get("thumbnail")
            if not url:
                continue
            # the MEDIA record's own access statement governs the file
            licence = ((first.get("usage") or {}).get("access") or "")
            candidates.append(Candidate(
                source=self.name,
                source_id=str(row.get("id") or first.get("idsId") or ""),
                source_url=descriptive.get("record_link", ""),
                download_url=url,
                kind="image",
                creator=(descriptive.get("data_source") or "Smithsonian Institution"),
                license=licence,
                source_tags=" ".join(filter(None, [
                    row.get("title", ""),
                    descriptive.get("data_source", ""),
                    " ".join(str(t) for t in (content.get("freetext") or {}).get("topic", [])
                             if isinstance(t, (str, int))),
                ])),
                thumbnail_url=first.get("thumbnail", ""),
                extra={
                    "unit_code": row.get("unitCode", ""),
                    # object-level rights, for reading only — the media
                    # record's statement is what governs the file
                    "object_access": ((descriptive.get("metadata_usage") or {})
                                      .get("access") or ""),
                },
            ))
        return filter_candidates(candidates)

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        import requests

        out_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(candidate.download_url, timeout=180,
                                headers={"User-Agent": _UA})
        response.raise_for_status()
        out_path.write_bytes(response.content)
        return out_path
