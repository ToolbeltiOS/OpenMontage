"""The New York Public Library Digital Collections.

Nine hundred thousand digitised items, heavy in photographs, maps and prints.
Needs a free token sent as `Authorization: Token token="..."`; without one the
API answers 401 and this adapter reports itself unavailable.

THE RIGHTS FIELD IS A SENTENCE, NOT A CODE
------------------------------------------
NYPL answers with `rightsStatement` as prose — "The New York Public Library
believes that this item is in the public domain under the laws of the United
States", or a paragraph about third-party rights. There is no vocabulary to
match against, so the sentence goes to the filter, which reads "public domain"
and "no known copyright" as permission and anything it cannot read as refusal.

That is the right way round for this source: NYPL's own public-domain
determinations are stated plainly, and everything else it holds is a question
for a human.

CAPTURES, NOT ITEMS. An item is a record; the FILES hang off its captures, and
an item with no capture has nothing to download. The adapter asks for the
item's captures and takes the first with an image derivative.
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://api.repo.nypl.org/api/v2/items/search"
_UA = "OpenMontage/1.0 (documentary asset bank)"
ENV_KEY = "NYPL_API_TOKEN"


def _get(url: str, params: dict | None = None, timeout: int = 60) -> dict:
    import requests

    token = os.environ.get(ENV_KEY, "")
    response = requests.get(
        url, params=params, timeout=timeout,
        headers={"User-Agent": _UA,
                 "Authorization": f'Token token="{token}"'})
    response.raise_for_status()
    return response.json()


class Nypl:
    name = "nypl"
    display_name = "NYPL Digital Collections"
    priority = 25
    supports = {"image": True, "video": False, "no_api_key": False}
    install_instructions = (
        f"Set {ENV_KEY} in .env to enable NYPL Digital Collections "
        "(free token at https://api.repo.nypl.org/)."
    )

    def is_available(self) -> bool:
        return bool(os.environ.get(ENV_KEY))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        if not os.environ.get(ENV_KEY) or filters.kind == "video":
            return []
        per_page = max(filters.per_page, 1)
        found = _get(_SEARCH, {
            "q": query,
            "per_page": per_page,
            "page": max(filters.page, 1),
        })
        response = (found.get("nyplAPI") or {}).get("response") or {}
        results = (response.get("result") or [])
        if isinstance(results, dict):
            results = [results]

        candidates: list[Candidate] = []
        for item in results:
            uuid = item.get("uuid") or ""
            image = (item.get("imageID") or "")
            url = (f"https://images.nypl.org/index.php?id={image}&t=w"
                   if image else "")
            if not url:
                continue
            candidates.append(Candidate(
                source=self.name,
                source_id=str(uuid),
                source_url=f"https://digitalcollections.nypl.org/items/{uuid}",
                download_url=url,
                kind="image",
                creator=item.get("Collection", {}).get("title", "")
                if isinstance(item.get("Collection"), dict) else "The New York Public Library",
                # prose, deliberately: there is no vocabulary to match
                license=str(item.get("rightsStatement") or ""),
                source_tags=" ".join(str(item.get(k, "")) for k in
                                     ("title", "typeOfResource", "dateDigitized")),
                thumbnail_url=(f"https://images.nypl.org/index.php?id={image}&t=t"
                               if image else ""),
                extra={"uuid": uuid, "image_id": image},
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
