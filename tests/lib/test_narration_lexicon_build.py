"""Deriving the lexicon: does a name the voice says right get left alone?

THE FIXTURES ARE REAL MEASUREMENTS, NOT INVENTED STRINGS. Every (name,
heard) pair below is what faster-whisper actually returned for king-tut
narration on 2026-11-10, and the classifier's two thresholds were chosen
against this table. If a later change to `normalise` moves one of these
rows across a band, that is the regression these tests exist to catch.

The table is also the argument for the middle band. The most distant
CORRECT reading here (Fellowes -> "Fellows") scores further from its name
than the closest WRONG one (Aspergillus -> "a spergulus"), so no single
threshold can split them, and a classifier with two answers would have to
either invent entries or silently miss them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import narration_lexicon as NL  # noqa: E402

#: Said correctly. The transcriber chose its own spelling for the sound.
HEARD_RIGHT = [
    ("Saqqara", "Radon at Sakara"),
    ("haematopoietic", "a hematopoietic cause"),
    ("Reid", "Douglas Reed wrote"),
    ("Bethell", "Richard Bethel died"),
    ("Giza", "readings at Giza"),
    ("flavus", "aspergillus flavus may"),
    ("Carnarvon", "the fifth Earl of Carnarvon"),
    ("Gould", "George J. Gould died that May"),
    ("Geiger", "He points to Geiger readings"),
    ("Weigall", "Arthur Weigal of the Daily Mail"),
]

#: Said wrongly. A different word came out.
HEARD_WRONG = [
    ("Gould", "The death of good was reported"),
    ("Geiger", "They took Jyga readings at Giza"),
    ("Weigall", "The Uyghal of the Daily Mail"),
    ("Tutankhamun", "created by shooting Cammon's priests"),
    ("erysipelas", "pneumonia supervening on facial ericyplers"),
    ("Carnarvon", "he had watched Knavon joking"),
    ("Tutankhamun", "created by two Tenkamun's priests"),
]

#: Neither band. Reported for a ruling; nothing is written.
BORDERLINE = [
    ("Fellowes", "Colonel Aubrey Fellows died"),
    ("Aspergillus", "spores of a spergulus flavus"),
]


class TestANameSaidRightGetsNoEntry:
    @pytest.mark.parametrize("name,heard", HEARD_RIGHT)
    def test_a_spelling_variant_is_clean(self, name, heard):
        assert NL.classify(name, heard) == "clean", \
            (name, heard, NL.distance_ratio(name, heard))

    def test_and_so_build_writes_nothing_for_it(self):
        out = NL.build(["Saqqara"], {"Saqqara": "sa-KAR-ah"},
                       say=lambda t, g: None,
                       transcribe=lambda g: "Radon at Sakara")
        assert out["entries"] == []
        assert [r["word"] for r in out["clean"]] == ["Saqqara"]

    def test_a_guide_does_not_force_an_entry(self):
        """A pronunciation_guide is permission to respell, not a reason to.

        The script director asks for a guide on every name the voice is
        LIKELY to mangle. Most of those turn out fine, and respelling one
        that was already right replaces a correct reading with a guess.
        """
        out = NL.build(["Giza"], {"Giza": "GEE-zah"},
                       say=lambda t, g: None,
                       transcribe=lambda g: "readings at Giza")
        assert out["entries"] == []


class TestANameTheVoiceManglesGetsOne:
    @pytest.mark.parametrize("name,heard", HEARD_WRONG)
    def test_a_different_word_is_misheard(self, name, heard):
        assert NL.classify(name, heard) == "misheard", \
            (name, heard, NL.distance_ratio(name, heard))

    def test_build_respells_it_from_the_guide(self):
        heard = {"probe_Tutankhamun": "created by shooting Cammon's priests",
                 "cand_Tutankhamun_tootankahmoon": "The name is Tutankhamun."}
        out = NL.build(["Tutankhamun"], {"Tutankhamun": "too-tan-KAH-moon"},
                       say=lambda t, g: None,
                       transcribe=lambda g: heard[g])
        assert len(out["entries"]) == 1
        entry = out["entries"][0]
        assert entry["word"] == "Tutankhamun"
        assert entry["say"] == "tootankahmoon"
        assert entry["respelled"] is True
        assert entry["misheard_as"] == "created by shooting Cammon's priests"

    def test_the_respelling_is_verified_not_just_generated(self):
        """A candidate that still reads wrong is NOT written.

        This is the whole difference between this step and a hand process
        that trusted the guide. "guyger" for Geiger is a reasonable reading
        of a guide and Kokoro says "guide your".
        """
        heard = {"probe_Geiger": "They took Jyga readings",
                 "cand_Geiger_guyger": "They took Guide your readings"}
        out = NL.build(["Geiger"], {"Geiger": "guy-ger"},
                       say=lambda t, g: None,
                       transcribe=lambda g: heard[g])
        assert out["entries"] == []
        assert len(out["unresolved"]) == 1
        assert out["unresolved"][0]["tried"][0]["say"] == "guyger"

    def test_misheard_with_no_guide_is_unresolved_not_invented(self):
        out = NL.build(["Weigall"], {},
                       say=lambda t, g: None,
                       transcribe=lambda g: "The Uyghal of the Daily Mail")
        assert out["entries"] == []
        assert "pronunciation_guide" in out["unresolved"][0]["why"]


class TestTheMiddleBandIsReportedNotGuessed:
    @pytest.mark.parametrize("name,heard", BORDERLINE)
    def test_it_is_uncertain(self, name, heard):
        assert NL.classify(name, heard) == "uncertain", \
            (name, heard, NL.distance_ratio(name, heard))

    def test_nothing_is_written_for_it(self):
        out = NL.build(["Fellowes"], {"Fellowes": "FEL-ohz"},
                       say=lambda t, g: None,
                       transcribe=lambda g: "Colonel Aubrey Fellows died")
        assert out["entries"] == []
        assert out["clean"] == []
        assert out["uncertain"][0]["word"] == "Fellowes"
        assert "ratio" in out["uncertain"][0]

    def test_the_bands_cannot_be_collapsed_into_two(self):
        """The measurement that forces three answers, asserted as a fact.

        Aspergillus was really said "a spergulus", which is WRONG, and it
        scores NEARER its name than Fellowes -> "Fellows" does, which is
        RIGHT. Any single threshold therefore either respells Fellowes or
        passes over Aspergillus. That is why there is a middle band, and
        this is the inequality that makes the argument.
        """
        wrong = NL.distance_ratio("Aspergillus", "spores of a spergulus flavus")
        right = NL.distance_ratio("Fellowes", "Colonel Aubrey Fellows died")
        assert wrong < right, (wrong, right)
        assert NL.CLEAN_BELOW <= wrong < NL.MISHEARD_AT
        assert NL.CLEAN_BELOW <= right < NL.MISHEARD_AT


class TestGuideToRespelling:
    def test_the_notation_is_stripped(self):
        assert NL.candidates_from_guide("too-tan-KAH-moon") == ["tootankahmoon"]

    def test_every_candidate_is_letters_only(self):
        for guide in ("kar-NAR-von", "em-BED-ings", "sa-KAR-ah",
                      "ˌæspərˈdʒɪləs", "er-ih-SIP-uh-las"):
            for cand in NL.candidates_from_guide(guide):
                assert NL.is_letters_only(cand), (guide, cand)

    def test_an_ipa_guide_degenerates_and_verification_catches_it(self):
        """IPA stripped of its marks is consonant mush, and that is fine.

        "/tuːtənˈkɑːmən/" reduces to "tutnkmn", which passes letters-only
        and spells nothing. Nothing downstream trusts it: the candidate is
        SAID and transcribed before it is written, so a guide in the wrong
        notation ends as an unresolved name the writer is told about, not
        as a respelling in the film. Verification is what makes a bad
        candidate generator safe.
        """
        assert NL.candidates_from_guide("/tuːtənˈkɑːmən/") == ["tutnkmn"]
        heard = {"probe_Tutankhamun": "created by shooting Cammon's priests",
                 "cand_Tutankhamun_tutnkmn": "The name is Tutt Nickman."}
        out = NL.build(["Tutankhamun"], {"Tutankhamun": "/tuːtənˈkɑːmən/"},
                       say=lambda t, g: None,
                       transcribe=lambda g: heard[g])
        assert out["entries"] == []
        assert out["unresolved"][0]["word"] == "Tutankhamun"


class TestMergingShared:
    SHARED = {"entries": [{"word": "Tutankhamun", "say": "tootankahmoon",
                           "respelled": True}]}

    def test_a_film_overrides_the_shared_entry(self):
        film = {"entries": [{"word": "Tutankhamun", "say": "tootankamoon",
                             "respelled": True}]}
        merged = NL.merge(self.SHARED, film)
        assert len(merged["entries"]) == 1
        assert merged["entries"][0]["say"] == "tootankamoon"

    def test_a_film_adds_to_it(self):
        film = {"entries": [{"word": "Weigall", "say": "wygawl",
                             "respelled": True}]}
        merged = NL.merge(self.SHARED, film)
        assert {e["word"] for e in merged["entries"]} == {"Tutankhamun",
                                                          "Weigall"}

    def test_a_missing_film_lexicon_leaves_the_shared_one(self):
        assert NL.merge(self.SHARED) == self.SHARED


class TestValidateRefusesNotation:
    def test_a_hyphenated_respelling_is_refused(self):
        bad = {"entries": [{"word": "Carnarvon", "say": "kar-NAR-von",
                            "respelled": True}]}
        assert NL.validate(bad)

    def test_a_capitalised_respelling_is_refused(self):
        bad = {"entries": [{"word": "Gould", "say": "GOOLD",
                            "respelled": True}]}
        assert NL.validate(bad)

    def test_the_real_shared_lexicon_passes(self):
        import json
        lex = json.loads((ROOT / "assets" / "narration" /
                          "lexicon.json").read_text())
        assert NL.validate(lex) == []


class TestSynthesisActuallySpeaksIt:
    """A lexicon nothing applies is the fourth asset-without-a-consumer.

    Three gates have already been built in this repo with nothing feeding
    them. A pronunciation lexicon that sits in assets/ while the synthesiser
    reads the raw script is the same mistake in a different shape, so these
    tests are about the WIRING, not the data.
    """

    @staticmethod
    def _source() -> list[str]:
        """Code lines only — a comment that mentions NL.apply is not a call.

        Twice in this repo a test has passed against a comment: the
        caffeinate check and the "all four loaded" check both matched prose
        describing the thing they were meant to verify.
        """
        src = (ROOT / "scripts" / "synthesize_narration.py").read_text()
        return [ln for ln in src.splitlines()
                if ln.strip() and not ln.strip().startswith("#")]

    def test_both_tts_call_sites_speak_the_respelled_text(self):
        calls = [ln for ln in self._source() if "tts(" in ln and "def " not in ln]
        assert calls, "no tts call sites found at all"
        assert all("NL.apply" in ln for ln in calls), calls

    def test_the_calibration_path_is_one_of_them(self):
        """Calibration measures wpm, and a respelling changes duration."""
        calib = [ln for ln in self._source()
                 if "_calib_" in ln or ("tts(" in ln and "body_speed" in ln)]
        assert any("NL.apply" in ln for ln in calib), calib

    def test_it_refuses_a_lexicon_it_cannot_speak(self, tmp_path,
                                                  monkeypatch):
        """Shipping "kar-NAR-von" is worse than the fault it was fixing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_syn", ROOT / "scripts" / "synthesize_narration.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        monkeypatch.setattr(mod, "ROOT", tmp_path)
        shared = tmp_path / "assets" / "narration"
        shared.mkdir(parents=True)
        (shared / "lexicon.json").write_text(json.dumps({"entries": [
            {"word": "Carnarvon", "say": "kar-NAR-von", "respelled": True}]}))
        with pytest.raises(SystemExit):
            mod.lexicon(tmp_path / "projects" / "whatever")

    def test_it_accepts_the_real_one(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_syn2", ROOT / "scripts" / "synthesize_narration.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        lex = mod.lexicon(tmp_path)          # no film lexicon: shared only
        assert {e["word"] for e in lex["entries"]} >= {"Tutankhamun", "Gould"}

    def test_the_script_text_itself_is_never_rewritten(self):
        """Captions, listing, alignment and the fact gate read the SCRIPT.

        Only the string handed to the synthesiser changes. If the lexicon
        were applied to the script, "tootankahmoon" would reach the screen.
        """
        lex = {"entries": [{"word": "Tutankhamun", "say": "tootankahmoon",
                            "respelled": True}]}
        original = "The tomb of Tutankhamun was opened."
        spoken = NL.apply(original, lex)
        assert spoken != original
        assert original == "The tomb of Tutankhamun was opened."
        assert "Tutankhamun" in original


class TestTheDerivationIsWiredIn:
    def test_the_weekly_asset_stage_derives_the_lexicon(self):
        body = "\n".join(
            ln for ln in (ROOT / "scripts" / "run_weekly.sh").read_text(
            ).splitlines() if not ln.strip().startswith("#"))
        assert "scripts/build_narration_lexicon.py --project $SLUG" in body

    def test_the_director_sends_the_writer_to_a_guide_not_a_respelling(self):
        """The one instruction that keeps the pipeline honest.

        A writer who writes the letters-only form by hand has guessed it,
        and an unmeasured respelling is how "guyger" ships.
        """
        # whitespace-flattened: a hard-wrapped markdown line puts a newline
        # anywhere, and a test that depends on the wrap tests the wrap
        doc = " ".join((ROOT / "skills" / "pipelines" /
                        "narrated-documentary" /
                        "script-director.md").read_text().split())
        assert "build_narration_lexicon.py" in doc
        assert "do **not** write IPA" in doc
        assert "letters-only form yourself" in doc

    def test_the_director_says_the_script_text_is_untouched(self):
        doc = (ROOT / "skills" / "pipelines" / "narrated-documentary" /
               "script-director.md").read_text()
        assert "only what is" in doc and "spoken" in doc.lower()
