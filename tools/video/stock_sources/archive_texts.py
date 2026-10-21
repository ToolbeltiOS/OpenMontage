"""Plates out of scanned books on the Internet Archive.

WHY A SEPARATE ADAPTER FROM archive_org.py
------------------------------------------
That one searches moving images. This one searches TEXTS, which is a different
thing wearing the same API: a text is a book, a book is three hundred page
scans, and almost all of them are pages of type that are of no use to a film.
What a documentary wants out of Petrie's 1883 Gizeh volume is the PLATES — the
sections, the elevations, the measured drawings — which are perhaps twenty
pages of the three hundred and are not listed anywhere.

So the adapter's real work is not searching. It is deciding which page of a
book is a picture.

HOW A PLATE IS TOLD FROM A PAGE
-------------------------------
Two measurements, and neither alone is enough:

  INK      what fraction of the page is not paper. A page of type runs about
           0.05-0.12; a plate with a large drawing on it runs higher, but so
           does a page of dense footnotes.
  WORDS    how many words OCR reads. A page of type gives two or three
           hundred; a plate gives a caption and a few labels.

A plate is a page with FEW WORDS and ENOUGH INK. Either test on its own is
wrong in a way that matters: ink alone keeps the footnote pages, and words
alone keeps the blank leaves and the title page.

RIGHTS
------
A scan's own `licenseurl`, or `possible-copyright-status` when there is no
licence URL — NOT_IN_COPYRIGHT is the Archive saying it has made the
determination. Anything else goes to the filter as it stands, and the filter
refuses what it cannot read.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Candidate, SearchFilters
from .licences import filter_candidates

_SEARCH = "https://archive.org/advancedsearch.php"
_METADATA = "https://archive.org/metadata"
_PAGE = "https://archive.org/download/{identifier}/page/n{page}_w{width}.jpg"
_UA = "OpenMontage/1.0 (documentary asset bank)"

#: Sixty seconds. The Archive's search is usually under half a second and
#: occasionally is not — it timed out on two endpoints during this work and
#: answered in 0.42s an hour later. A short timeout turns a slow day into an
#: empty catalogue.
TIMEOUT_S = 60

#: Width to fetch a page at while deciding whether it is a plate. Big enough
#: for OCR to read a caption, small enough to scan a book in a few minutes.
PROBE_WIDTH = 800

#: And the width to fetch a page that turned out to be one.
PLATE_WIDTH = 2400

#: A page with more words than this is type, whatever its ink says.
MAX_WORDS_ON_A_PLATE = 40

#: ...and one with less ink than this is blank, whatever its words say.
MIN_INK_ON_A_PLATE = 0.035

#: INK IS MEASURED AGAINST THE PAGE'S OWN PAPER, NOT AN ABSOLUTE LEVEL.
#:
#: The first version counted pixels darker than 190 on a 0-255 page, which
#: works on a clean scan and is nonsense on a toned one. Petrie's 1883 Gizeh
#: volume on the Archive is TWO SCANS in one item: most of it is a 1908px
#: greyscale with white paper, and some of it is a 1196px colour scan whose
#: paper sits at 170. On those pages "darker than 190" measured the PAPER,
#: returned 0.70, and called a page of numerical tables a plate.
#:
#: So the threshold is a fraction of the page's own contrast, between its
#: paper and its darkest ink.
INK_THRESHOLD_FRACTION = 0.45

#: A page whose paper and ink are closer together than this has nothing on
#: it; without the test a blank leaf's sensor noise splits into "ink".
MIN_PAGE_CONTRAST = 40

#: Leaves at each end of a scan that are not pages of the book.
#:
#: A scan begins and ends with the binding and the library's own paper: a
#: bookplate, a barcode, a date-due slip. A date-due slip is sparse text in
#: ruled boxes, which is what a sparse plate looks like to both measurements
#: — it scored ink 0.037 against a floor of 0.035 and 33 words against a
#: ceiling of 40, and was the only false positive in two scans of this book.
#: It is not a borderline plate, it is not part of the book, and tuning the
#: thresholds to exclude it would have excluded sparse plates with it.
SKIP_LEAVES = 4

#: ...and a page with no genuinely DARK pixel has nothing printed on it,
#: however much its paper varies.
#:
#: This is the test that relative measurement needs beside it. A blank toned
#: leaf measured 0.35 "ink", because the threshold is a fraction of the
#: page's own contrast and that page's contrast was its own mottling. Real
#: ink is dark in absolute terms: on this book's pages the 2nd percentile is
#: 0-70 wherever anything is printed and 147-179 on the blank leaves.
MAX_DARKEST_ON_A_PRINTED_PAGE = 120

#: OCR sees a normalised, upscaled page for the same reason. The colour scan
#: above returned ZERO words on a page of dense type, because it is smaller
#: and flatter than the greyscale one, and zero words is what a plate looks
#: like.
OCR_MIN_WIDTH = 1600

#: Everything is measured on the middle of the scan, not the whole frame.
#:
#: A scan has the page in it and it has the SCANNER in it: a white surround,
#: a dark gutter, sometimes a colour target. On the toned pages that surround
#: is pure white, so "the page's own paper level" taken over the whole frame
#: came back 255 — the colour of the border — and the page itself was
#: measured as ink. Cropping first is what makes "relative to the page" mean
#: the page.
PAGE_INTERIOR = 0.80


def _get(url: str, params: dict | None = None, timeout: int = TIMEOUT_S):
    import requests

    response = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": _UA})
    response.raise_for_status()
    return response


def metadata(identifier: str) -> dict:
    return _get(f"{_METADATA}/{identifier}").json()


def rights_of(meta: dict) -> str:
    """The scan's own statement, in the order the Archive prefers them."""
    fields = meta.get("metadata") or {}
    for key in ("licenseurl", "rights", "possible-copyright-status"):
        value = fields.get(key)
        if value:
            return str(value if not isinstance(value, list) else value[0])
    return ""


def page_url(identifier: str, page: int, width: int = PROBE_WIDTH) -> str:
    return _PAGE.format(identifier=identifier, page=page, width=width)


def measure_page(path: Path) -> dict:
    """Ink coverage and word count for one page scan.

    Both measurements are made relative to the page rather than to a constant,
    because a book on the Archive is not one scan — see the two constants
    above and what they cost to learn.
    """
    import numpy as np
    import pytesseract
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        grey = image.convert("L")
        width, height = grey.size
        margin_x = int(width * (1 - PAGE_INTERIOR) / 2)
        margin_y = int(height * (1 - PAGE_INTERIOR) / 2)
        interior = grey.crop((margin_x, margin_y, width - margin_x, height - margin_y))
        array = np.asarray(interior, dtype="uint8")

        # the paper is the commonest tone on the page, not the brightest
        # thing in the scan
        counts = np.bincount(array.reshape(-1), minlength=256)
        paper = float(np.argmax(counts))
        darkest = float(np.percentile(array, 2))
        contrast = paper - darkest
        if contrast < MIN_PAGE_CONTRAST or darkest > MAX_DARKEST_ON_A_PRINTED_PAGE:
            ink = 0.0                      # a blank leaf
        else:
            threshold = paper - INK_THRESHOLD_FRACTION * contrast
            ink = float((array < threshold).mean())

        # give OCR a page it can read: normalised, and big enough
        legible = ImageOps.autocontrast(interior, cutoff=1)
        if legible.width < OCR_MIN_WIDTH:
            scale = OCR_MIN_WIDTH / legible.width
            legible = legible.resize(
                (OCR_MIN_WIDTH, round(legible.height * scale)), Image.LANCZOS)
        text = pytesseract.image_to_string(legible)

    words = len([w for w in text.split() if any(c.isalnum() for c in w)])
    return {"ink": round(ink, 4), "words": words,
            "paper": round(paper, 1), "contrast": round(contrast, 1)}


def is_a_plate(measured: dict) -> bool:
    """Few words, enough ink. Either test alone keeps the wrong pages."""
    return (measured["words"] <= MAX_WORDS_ON_A_PLATE
            and measured["ink"] >= MIN_INK_ON_A_PLATE)


def find_plates(identifier: str, into: Path, pages: range | None = None,
                limit: int = 40) -> list[dict]:
    """Walk a book's pages and keep the ones that are pictures."""
    meta = metadata(identifier)
    count = int((meta.get("metadata") or {}).get("imagecount") or 0)
    pages = pages if pages is not None else range(count)
    first, last = SKIP_LEAVES, max(SKIP_LEAVES, count - SKIP_LEAVES)
    into.mkdir(parents=True, exist_ok=True)

    found: list[dict] = []
    for page in pages:
        if count and not (first <= page < last):
            continue                       # binding and library matter
        if len(found) >= limit:
            break
        probe = into / f"probe_{page:04d}.jpg"
        try:
            probe.write_bytes(_get(page_url(identifier, page)).content)
        except Exception:
            continue                       # a missing leaf is not a failure
        measured = measure_page(probe)
        measured.update({"page": page, "identifier": identifier})
        if is_a_plate(measured):
            found.append(measured)
        probe.unlink(missing_ok=True)
    return found


class ArchiveTexts:
    name = "archive_texts"
    display_name = "Internet Archive (book plates)"
    priority = 26
    supports = {"image": True, "video": False, "no_api_key": True}
    install_instructions = "No API key required."

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        """Books matching the query, as candidates for plate extraction.

        A candidate here is a BOOK, not a page: deciding which pages are
        plates costs one fetch and one OCR pass per page, which is not
        something to do for every search result. `find_plates` is the second
        step and the caller asks for it.
        """
        if filters.kind == "video":
            return []
        per_page = max(filters.per_page, 1)
        found = _get(_SEARCH, {
            "q": f'{query} AND mediatype:texts',
            "fl[]": ["identifier", "title", "year", "creator"],
            "rows": per_page,
            "page": max(filters.page, 1),
            "output": "json",
        }).json()

        candidates: list[Candidate] = []
        for doc in ((found.get("response") or {}).get("docs") or []):
            identifier = doc.get("identifier")
            if not identifier:
                continue
            try:
                meta = metadata(identifier)
            except Exception:
                continue
            candidates.append(Candidate(
                source=self.name,
                source_id=str(identifier),
                source_url=f"https://archive.org/details/{identifier}",
                download_url=page_url(identifier, 0, PLATE_WIDTH),
                kind="image",
                creator=str(doc.get("creator") or "Internet Archive"),
                license=rights_of(meta),
                source_tags=" ".join(str(doc.get(k, "")) for k in
                                     ("title", "creator", "year")),
                thumbnail_url=f"https://archive.org/services/img/{identifier}",
                extra={
                    "identifier": identifier,
                    "year": doc.get("year"),
                    "pages": (meta.get("metadata") or {}).get("imagecount"),
                    "is_a_book": True,
                    "plates_found_by": "tools/video/stock_sources/archive_texts.py",
                },
            ))
        return filter_candidates(candidates)

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(_get(candidate.download_url, timeout=180).content)
        return out_path
