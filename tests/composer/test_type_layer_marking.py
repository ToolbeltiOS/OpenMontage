"""Every element that paints words carries the type class.

The film renders twice from one tree: once with the type laid out but not
inked, which the shader runs over, and once with only the type, over
transparency. The split is a single class, `om-type`, on every text element —
so an element nobody marked is not merely unmarked. It is baked into the
plate: grain on its edges, drifting with the plate, underneath locked type
saying the same words.

Eleven such elements were found by hand when the split was built, the last of
them by reading a rendered frame. This finds them by reading the source, which
is faster and does not wait for a scene to appear in a demo.

The rule is approximated as: a JSX element whose inline style sets a font
family, or an SVG <text>, paints text. That over-reaches in one direction — a
container can set a font for its descendants without painting any itself — so
the containers that legitimately do are listed by name, with the reason.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"

#: Vendored code, which is not ours to mark.
SKIP_DIRS = {"transitions"}

#: Files in the film's own tree that are never rendered through the two-pass
#: split, so the class would mean nothing on them.
#:
#: The rule is about elements inside a `<LayerScope>`. A thumbnail is its own
#: composition, rendered once as a still: there is no plate pass to keep its
#: title out of, and marking it `om-type` would claim a split that does not
#: happen. Listed by name with the reason rather than skipped by a pattern,
#: so the next file that wants out has to argue for it.
NOT_IN_THE_LAYERED_RENDER = {"Thumbnail.tsx"}

#: Containers that set a font family for their descendants without painting
#: any text themselves.
ALLOWED: set[tuple[str, str]] = {
    # the composition root: the film's default family, for everything in it
    ("Explainer.tsx", "fontFamily: theme.headingFont || fontFamily"),
}


def without_comments(source: str) -> str:
    """Blank out comments, preserving offsets so line numbers still hold.

    Without this the scan reads the rule's own documentation — `layers.tsx`
    explains itself using the words "SVG `<text>`" — and reports the
    explanation as an unmarked element.
    """
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    source = re.sub(r"/\*.*?\*/", blank, source, flags=re.S)
    return re.sub(r"(?<![:\w])//[^\n]*", blank, source)


def jsx_sites(source: str) -> list[tuple[int, str, bool]]:
    """(offset, tag name, marked) for every element that paints text."""
    source = without_comments(source)
    sites = []
    for m in re.finditer(r"<text(?=[\s>])", source):
        close = source.find(">", m.start())
        head = source[m.start():close + 1 if close > 0 else m.start() + 200]
        sites.append((m.start(), "text", "TYPE_CLASS" in head))
    for m in re.finditer(r"style=\{\{", source):
        depth, k = 2, m.end()
        while k < len(source) and depth:
            depth += {"{": 1, "}": -1}.get(source[k], 0)
            k += 1
        if "fontFamily" not in source[m.end():k]:
            continue
        start = source.rfind("<", 0, m.start())
        while start > 0 and not re.match(r"<[A-Za-z][\w.]*[\s>]", source[start:start + 40]):
            start = source.rfind("<", 0, start)
        name = re.match(r"<([A-Za-z][\w.]*)", source[start:])
        head = source[start:m.start()]
        sites.append((start, name.group(1) if name else "?",
                      "TYPE_CLASS" in head or "className" in head))
    return sites


def line_of(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def allowed(path: Path, source: str, offset: int) -> bool:
    block = source[offset:offset + 600]
    return any(path.name == name and key in block for name, key in ALLOWED)


def in_documentary_tree(path: Path) -> bool:
    """Is this file part of the film, as opposed to the short-form library?

    The split only exists inside a `<LayerScope>`, and only the documentary
    composition opens one — a lyric overlay or a product reveal renders flat
    and always has. The two are told apart by the design system: everything
    in the film either lives in `design/` or `scenes/` or imports from
    `design/`, and nothing in the short-form library does.
    """
    relative = path.relative_to(SRC)
    if relative.parts[0] in ("design", "scenes"):
        return True
    return bool(re.search(r'from "[^"]*design/', path.read_text()))


def tsx_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.tsx")
                  if not SKIP_DIRS & set(p.relative_to(SRC).parts)
                  and p.name not in NOT_IN_THE_LAYERED_RENDER
                  and in_documentary_tree(p))


@pytest.mark.parametrize("path", tsx_files(), ids=lambda p: p.name)
def test_every_text_element_is_marked_as_type(path):
    source = path.read_text()
    missing = [f"{path.name}:{line_of(source, off)} <{name}>"
               for off, name, marked in jsx_sites(source)
               if not marked and not allowed(path, source, off)]
    assert not missing, (
        "these paint text but carry no TYPE_CLASS, so they would be baked "
        "into the plate and grained: " + ", ".join(missing))


def test_the_scan_finds_the_text_it_is_supposed_to():
    """A guard on the guard: a scanner that matches nothing passes everything."""
    found = sum(len(jsx_sites(p.read_text())) for p in tsx_files())
    assert found > 40, f"only {found} text elements found; the scan is broken"


def test_the_short_form_library_is_deliberately_out_of_scope():
    """It renders flat, outside any LayerScope, and always has."""
    outside = [p.name for p in SRC.rglob("*.tsx")
               if not SKIP_DIRS & set(p.relative_to(SRC).parts)
               and not in_documentary_tree(p)]
    assert "StatCard.tsx" in outside and "LyricOverlay.tsx" in outside
    assert "Explainer.tsx" not in outside
