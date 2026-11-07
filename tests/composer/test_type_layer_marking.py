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
    """It renders flat, outside any LayerScope, and always has.

    `StatCard.tsx` used to be the example here, and that is the assertion
    that let king-tut ship a plate with 119 legible words in it: the file
    was out of scope because it imported nothing from `design/`, and the
    test wrote that exclusion down as deliberate. It was never deliberate.
    The documentary composition dispatches `cut.type === "stat_card"` to it,
    so the moment an edit used that cut type the component was in the film —
    and the only thing that had to change for the exclusion to become a bug
    was a scene plan, in a different repository directory, months later.

    The example is now a file the film genuinely cannot reach.
    """
    outside = [p.name for p in SRC.rglob("*.tsx")
               if not SKIP_DIRS & set(p.relative_to(SRC).parts)
               and not in_documentary_tree(p)]
    assert "LyricOverlay.tsx" in outside
    assert "Explainer.tsx" not in outside
    assert "StatCard.tsx" not in outside and "TextCard.tsx" not in outside


# ---------------------------------------------------------------------------
# Which components the film can actually reach
# ---------------------------------------------------------------------------

#: Components the documentary composition dispatches a `cut.type` to, which
#: are NOT yet marked for the two-pass split.
#:
#: Every one of these is the king-tut bug waiting for a scene plan to pick
#: it: reachable from `Explainer`, painting words, carrying no `om-type`. The
#: list is not permission. It is the record of which cut types no film has
#: used yet, and `test_no_film_uses_an_unmarked_cut_type` fails the moment
#: one does — at edit time, before three hours of rendering.
UNMARKED_CUT_TYPES = {
    # Paints no text at all today — but it is not in the scan, so nothing
    # would notice if it started to. Listed rather than special-cased.
    "anime_scene": "AnimeScene.tsx",
    "comparison": "ComparisonCard.tsx",
    "hero_title": "HeroTitle.tsx",
    "kpi_grid": "KPIGrid.tsx",
    "progress_bar": "ProgressBar.tsx",
    "screenshot_scene": "ScreenshotScene.tsx",
    "terminal_scene": "TerminalScene.tsx",
}


def dispatched_cut_types() -> set[str]:
    """Every `cut.type` the documentary composition renders."""
    source = without_comments((SRC / "Explainer.tsx").read_text())
    return set(re.findall(r'cut\.type === "([a-z_]+)"', source))


def used_cut_types() -> dict[str, list[str]]:
    """Every `cut.type` any project's edit has actually asked for.

    ACROSS EVERY WORKTREE, because `projects/` is gitignored and each tree
    holds different films: the runner has king-tut, this one does not, and a
    check that read only its own directory would have passed on the very
    film it exists to catch.
    """
    import json
    import sys
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "lib"))
    from already_covered import worktree_roots

    out: dict[str, list[str]] = {}
    seen: set[str] = set()
    for root in worktree_roots(repo):
        for edit in sorted((root / "projects").glob("*/artifacts/edit_decisions.json")):
            film = edit.parent.parent.name
            if film in seen:
                continue            # the same film, checked out twice
            seen.add(film)
            try:
                cuts = json.loads(edit.read_text()).get("cuts") or []
            except (ValueError, OSError):
                continue
            for cut in cuts:
                kind = cut.get("type")
                if kind:
                    out.setdefault(kind, []).append(film)
    return out


def test_no_film_uses_an_unmarked_cut_type():
    """The control for king-tut, at the only moment it is cheap.

    king-tut's scene plan chose `text_card` and `stat_card` — seven cuts
    each, and the first film ever to use either. Nothing noticed until the
    delivery gates read the finished plate, two renders and most of a day
    later. This reads the edit instead.
    """
    used = used_cut_types()
    caught = {kind: (UNMARKED_CUT_TYPES[kind], sorted(set(films)))
              for kind, films in used.items() if kind in UNMARKED_CUT_TYPES}
    assert not caught, (
        "these films use a cut type whose component paints words with no "
        "TYPE_CLASS, so the words will be baked into the plate, grained, and "
        "will drift with the picture: " + "; ".join(
            f"{kind} -> {component} ({', '.join(films)})"
            for kind, (component, films) in sorted(caught.items())))


def test_the_unmarked_list_names_only_components_that_are_really_unmarked():
    """A quarantine list that goes stale stops meaning anything.

    If someone marks `HeroTitle` and leaves it listed here, the list claims a
    gap that is closed and the next reader trusts it less.
    """
    scanned = {p.name for p in tsx_files()}
    stale = sorted(name for name in UNMARKED_CUT_TYPES.values()
                   if name in scanned)
    assert not stale, (
        "these are marked and scanned now; take them off UNMARKED_CUT_TYPES: "
        + ", ".join(stale))


def test_every_dispatched_cut_type_is_accounted_for():
    """Either the component is scanned, or it is on the list with a name.

    A cut type that is neither is the state king-tut shipped in: nobody had
    decided anything about it, so nothing could fail.
    """
    scanned = {p.name for p in tsx_files()}
    # Which file a cut type renders is read from the dispatch itself, so a
    # new scene type cannot be added without this test seeing it.
    source = without_comments((SRC / "Explainer.tsx").read_text())
    unaccounted = []
    for kind in sorted(dispatched_cut_types()):
        if kind in UNMARKED_CUT_TYPES:
            continue
        # The first component tag after the branch opens. Not `[^;]*?`: the
        # `outro_cta` branch builds its props in several statements before
        # it returns, and a semicolon stopped the search short of the tag.
        start = source.find(f'cut.type === "{kind}"')
        window = source[start:start + 1600] if start >= 0 else ""
        m = re.search(r"<([A-Z][\w]*)", window)
        component = f"{m.group(1)}.tsx" if m else None
        if component is None or component not in scanned:
            unaccounted.append(f"{kind} -> {component or 'unknown component'}")
    assert not unaccounted, (
        "these cut types render through a component the type-class scan "
        "never reads, and they are not on UNMARKED_CUT_TYPES either: "
        + ", ".join(unaccounted))
