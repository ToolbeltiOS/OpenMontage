"""Europeana — aggregated European cultural heritage.

Fifty-odd million records from museums, libraries and archives across Europe.
Needs a free key; without one the API answers 401 and this adapter reports
itself unavailable.

WHY THE RIGHTS FIELD IS THE EASY PART AND THE HARD PART
-------------------------------------------------------
Europeana is one of the few APIs that states rights as a URI from a closed
vocabulary — `http://creativecommons.org/publicdomain/zero/1.0/`,
`.../licenses/by-nc-sa/4.0/`, `http://rightsstatements.org/vocab/InC/1.0/`.
That is the easy part: the string is unambiguous.

The hard part is that an aggregator's rights statement describes the record at
the PROVIDING institution, and the thing being downloaded is whatever
`edmIsShownBy` points at, which may be a different resolution on a different
server. The URI is passed to the filter as it stands, and the provider is
carried in `extra` so a rights question has somewhere to go back to.

NC AND ND ARRIVE HERE IN QUANTITY. More than half of Europeana's images carry
one or the other, and that is exactly what the filter is for — the URI form
`.../licenses/by-nc-sa/4.0/` contains "by", so a substring check for "CC BY"
would accept every one of them.
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://api.europeana.eu/record/v2/search.json"
_UA = "OpenMontage/1.0 (documentary asset bank)"
ENV_KEY = "EUROPEANA_API_KEY"


def _get(url: str, params: dict, timeout: int = 60) -> dict:
    import requests

    response = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": _UA})
    response.raise_for_status()
    return response.json()


def _first(value, default: str = "") -> str:
    """Europeana returns almost everything as a list of one."""
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value) if value else default


class Europeana:
    name = "europeana"
    display_name = "Europeana"
    priority = 24
    supports = {"image": True, "video": False, "no_api_key": False}
    install_instructions = (
        f"Set {ENV_KEY} in .env to enable Europeana "
        "(free key at https://pro.europeana.eu/page/get-api)."
    )

    def is_available(self) -> bool:
        return bool(os.environ.get(ENV_KEY))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        key = os.environ.get(ENV_KEY)
        if not key or filters.kind == "video":
            return []
        per_page = max(filters.per_page, 1)
        found = _get(_SEARCH, {
            "wskey": key,
            "query": query,
            "media": "true",
            "qf": "TYPE:IMAGE",
            "rows": per_page,
            "start": (max(filters.page, 1) - 1) * per_page + 1,   # 1-based
            "profile": "rich",
        })

        candidates: list[Candidate] = []
        for item in found.get("items", []) or []:
            url = _first(item.get("edmIsShownBy")) or _first(item.get("edmPreview"))
            if not url:
                continue
            candidates.append(Candidate(
                source=self.name,
                source_id=str(item.get("id", "")),
                source_url=_first(item.get("guid")) or _first(item.get("edmIsShownAt")),
                download_url=url,
                kind="image",
                creator=_first(item.get("dcCreator")) or _first(item.get("dataProvider")),
                # a URI from a closed vocabulary; passed through as it stands
                license=_first(item.get("rights")),
                source_tags=" ".join(filter(None, [
                    _first(item.get("title")),
                    _first(item.get("dcDescription"))[:200],
                    _first(item.get("dataProvider")),
                    _first(item.get("country")),
                ])),
                thumbnail_url=_first(item.get("edmPreview")),
                extra={
                    "data_provider": _first(item.get("dataProvider")),
                    "country": _first(item.get("country")),
                    "rights_uri": _first(item.get("rights")),
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
