"""The page and the pinned comment are the same list, or they are a lie.

Attribution that disagrees with itself is worse than one copy of it: a
reader who checks two places and finds different films' worth of credits
cannot trust either. So both render from `build_listing.credits_rows` and
neither walks the asset bank, and this asserts it on the real props of all
four films rather than on a fixture.

CC BY 4.0 3(a)(2) is what makes the page sufficient on its own: the
required attribution may be given by "providing a URI or hyperlink to a
resource that includes the required information".
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))

import build_credits_page as P  # noqa: E402
import build_listing as L  # noqa: E402

FILMS = ("they-said-it-couldnt-be-built", "easter-island", "noah", "king-tut")


def records_for(slug: str):
    art = P.artifacts_for(slug)
    if art is None:
        pytest.skip(f"{slug} has no render_props.json in any worktree")
    props = json.loads((art / "render_props.json").read_text())
    return art, props, L.credits_rows(art, props)


@pytest.mark.parametrize("slug", FILMS)
def test_the_page_and_the_comment_list_identical_assets(slug):
    art, props, (records, att) = records_for(slug)
    block, block_att = L.credits_block(art, props)

    # NOT a line split: a key may itself span several lines. One Wikimedia
    # stitch names its nine source photographs one per line, which is how
    # the pinned comment ends up with orphan lines in it. Compared whole.
    header = "\n".join(block.split("\n")[:4])
    assert block == header + "\n" + "\n".join(r["key"] for r in records)
    assert att == block_att

    html = P.page_html("A film", "vid", records, att)
    # Every asset on the page, by the source URL that identifies it. An
    # asset with no page is identified by its title instead.
    for record in records:
        needle = record["page"] or record["title"].splitlines()[0]
        if needle:
            assert needle.replace("&", "&amp;") in html or needle in html, (
                f"{slug}: {needle!r} is in the comment and not on the page")
    assert html.count("<li>") == len(records), (
        f"{slug}: the page has {html.count('<li>')} rows for "
        f"{len(records)} credited assets")


@pytest.mark.parametrize("slug", FILMS)
def test_every_credited_asset_carries_a_licence_the_reader_can_open(slug):
    _, _, (records, _) = records_for(slug)
    assert records, f"{slug} credits nothing"
    missing = [r["licence"] for r in records if not r["deed"]]
    assert not missing, (
        f"{slug}: {len(missing)} asset(s) name a licence with no deed to "
        f"link: {sorted(set(missing))}")


@pytest.mark.parametrize("slug", FILMS)
def test_the_page_is_html_that_escapes_what_it_was_given(slug):
    _, _, (records, att) = records_for(slug)
    html = P.page_html("A film & <b>its</b> title", "vid", records, att)
    assert html.startswith("<!doctype html>")
    assert "A film &amp; &lt;b&gt;its&lt;/b&gt; title" in html
    # Nothing from the bank may close a tag it did not open.
    body = html[html.index("<ol>"):html.index("</ol>")]
    assert body.count("<li>") == body.count("</li>")
    assert "<script" not in html.lower()


class TestTheRecordsAreOneWalkAndNotTwo:
    def test_the_block_is_rendered_from_the_records(self):
        """If `credits_block` ever walks the bank again, the two can drift
        and this file stops meaning anything."""
        source = (ROOT / "scripts" / "build_listing.py").read_text()
        block_fn = source[source.index("def credits_block"):]
        block_fn = block_fn[:block_fn.index("\ndef ", 1)]
        assert "credits_rows(" in block_fn
        assert "asset_bank" not in block_fn, (
            "credits_block walks the bank itself again")

    def test_the_page_builder_does_not_walk_the_bank_either(self):
        source = (ROOT / "scripts" / "build_credits_page.py").read_text()
        assert "credits_rows" in source
        assert "asset_bank" not in source


class TestTheUrlIsPartOfThePublishedRecord:
    """Descriptions of films that are already live point at this string."""

    def test_the_site_is_the_published_one(self):
        assert P.SITE == "https://toolbeltios.github.io/wak3upsociety-credits"

    @pytest.mark.parametrize("slug", FILMS)
    def test_a_slug_maps_to_one_stable_url(self, slug):
        assert P.page_url(slug) == f"{P.SITE}/{slug}.html"
        assert " " not in P.page_url(slug)

    def test_the_index_links_every_film_it_is_given(self):
        films = [{"slug": "a", "title": "A", "assets": 1},
                 {"slug": "b", "title": "B", "assets": 2}]
        html = P.index_html(films)
        assert './a.html' in html and './b.html' in html
        assert html.count("<li>") == 2


class TestACreditThatSpansLines:
    """A Wikimedia stitch names each of its source photographs on its own
    line. In the pinned comment that is a run of orphan lines; on the page
    it has to be one row with nothing dropped."""

    RECORD = {
        "key": "k", "asset_id": "wm_1", "title": "File:Stitched.jpg",
        "artist": "a.jpg: Olaf Tausch\nb.jpg: Olaf Tausch\n"
                  "derivative work: Hic et nunc (talk)",
        "licence": "CC BY-SA 3.0",
        "deed": "https://creativecommons.org/licenses/by-sa/3.0/",
        "page": "https://commons.wikimedia.org/wiki/File:Stitched.jpg",
        "provider": "wikimedia", "notice": "", "kind": "asset",
    }

    def test_it_renders_as_one_row(self):
        row = P.row_html(self.RECORD)
        assert row.count("<li>") == 1 and row.count("</li>") == 1
        assert "\n" not in row

    def test_nothing_in_the_credit_is_dropped(self):
        row = P.row_html(self.RECORD)
        for part in ("a.jpg: Olaf Tausch", "b.jpg: Olaf Tausch",
                     "derivative work: Hic et nunc (talk)"):
            assert part in row, part

    def test_the_real_films_contain_such_a_credit(self):
        """The control: if no film has one, this class is testing a
        situation that does not arise."""
        found = 0
        for slug in FILMS:
            art = P.artifacts_for(slug)
            if art is None:
                continue
            records, _ = L.credits_rows(art, json.loads(
                (art / "render_props.json").read_text()))
            found += sum(1 for r in records if "\n" in r["artist"])
        assert found, "no film has a multi-line credit any more"
