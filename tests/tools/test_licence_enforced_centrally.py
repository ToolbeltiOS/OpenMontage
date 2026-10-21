"""The licence filter runs for every source, not for the ones that remember.

It was written into three museum adapters. Sixteen others never called it —
including the Library of Congress, whose own rights field says "varies, verify
per item" on everything that is not plainly public domain, and whose adapter
turned that into a licence string and passed it on.

So the filter moved to the fan-out in the corpus builder, where every source's
results go through it whether the adapter asked or not. These tests pin that:
an adapter cannot opt out, and an adapter that filters twice is unharmed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

import tools.video.stock_sources as stock_sources
from lib.corpus import Corpus
from tools.video.corpus_builder import CorpusBuilder
from tools.video.stock_sources.licences import classify, filter_candidates


@dataclass
class _Candidate:
    clip_id: str
    license: str
    extra: dict = field(default_factory=dict)


class _Source:
    """A source that has never heard of the licence filter."""

    name = "careless"

    def __init__(self, licences: list[str]) -> None:
        self.licences = licences

    def is_available(self) -> bool:
        return True

    def search(self, query, filters):
        return [_Candidate(f"clip-{i}", lic)
                for i, lic in enumerate(self.licences)]


@pytest.fixture
def run_builder(monkeypatch, tmp_path):
    def run(licences: list[str]):
        processed: list[str] = []

        class _Record:
            def __init__(self, clip_id):
                self.clip_id = clip_id

        def processor(self, cand, *args, **kwargs):
            processed.append(cand.clip_id)
            return _Record(cand.clip_id)

        monkeypatch.setattr(stock_sources, "available_sources",
                            lambda: [_Source(licences)])
        monkeypatch.setattr(stock_sources, "source_summary", lambda: {})
        monkeypatch.setattr(CorpusBuilder, "_process_candidate", processor)
        monkeypatch.setattr(Corpus, "has", lambda self, clip_id: False)
        monkeypatch.setattr(Corpus, "add", lambda self, rec: None, raising=False)
        result = CorpusBuilder().execute({
            "corpus_dir": str(tmp_path / "corpus"),
            "queries": [{"query": "a quarry"}],
            "max_new_clips": 50,
        })
        return result, processed

    return run


class TestEnforcement:
    def test_a_source_that_never_filters_is_filtered_anyway(self, run_builder):
        result, processed = run_builder([
            "CC0 1.0",                                  # keep
            "CC BY-NC 4.0",                             # monetised channel
            "CC BY-ND 4.0",                             # we re-cut and re-grade
            "Rights status varies — verify per item",   # the LoC string
            "",                                         # no rights field at all
        ])
        assert len(processed) == 1, processed
        assert result.data["licence_refused"] == 4

    def test_the_refusal_count_is_reported(self, run_builder):
        result, _ = run_builder(["CC BY-NC-SA 4.0", "CC BY 4.0"])
        assert result.data["licence_refused"] == 1
        assert result.data["candidates_seen"] == 1

    def test_nothing_is_refused_when_everything_is_permitted(self, run_builder):
        result, processed = run_builder([
            "CC0 1.0", "Public Domain Mark 1.0", "CC BY 4.0", "CC BY-SA 4.0"])
        assert result.data["licence_refused"] == 0
        assert len(processed) == 4

    def test_filtering_twice_changes_nothing(self):
        """Three adapters filter their own results and still do."""
        once = filter_candidates([_Candidate("a", "CC0 1.0"),
                                  _Candidate("b", "CC BY-NC 4.0")])
        twice = filter_candidates(list(once))
        assert [c.clip_id for c in once] == [c.clip_id for c in twice] == ["a"]
        assert twice[0].extra["licence_code"] == "CC0"


class TestTheLibraryOfCongressString:
    """The string that made this necessary."""

    def test_varies_verify_per_item_is_not_permission(self):
        assert not classify(
            "Rights status varies — verify per item (Library of Congress)").permitted

    def test_the_adapter_no_longer_invents_that_string(self):
        from tools.video.stock_sources import loc

        assert not hasattr(loc, "_LICENSE_CHECK"), (
            "the adapter still has a licence string for items whose rights it "
            "does not know; an unknown rights field is not a licence")
