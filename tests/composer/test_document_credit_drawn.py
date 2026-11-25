"""Every document card in a delivered slice draws its credit.

The other tests in this change read props and source. This one reads the
PICTURE: it OCRs the delivered frame at each `document_reveal` and looks
for the words the cut asked to have printed under its quotation.

It is the only way to be sure. The citation was authored correctly by the
edit stage for six films and lost in a `setdefault` on its way to the
renderer, and every check that stopped short of the frame agreed that
everything was fine.

SKIPS when no slice has been delivered on this machine. Rendering one
takes about twenty minutes, which is not a unit test — the merge procedure
renders it (`scripts/slice_check.py`) and this reads what came out.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

SLICE = Path("/private/tmp/openmontage-slices/attack-on-pearl-harbor-slice")
FILM = SLICE / "attack-on-pearl-harbor-slice.mp4"
PROPS = SLICE / "render_props.json"


def cards() -> list[tuple[dict, float]]:
    """Each document_reveal and a timestamp inside it."""
    props = json.loads(PROPS.read_text())
    out, clock = [], 0.0
    for cut in props["cuts"]:
        length = float(cut["out_seconds"]) - float(cut["in_seconds"])
        if cut.get("type") == "document_reveal":
            # Late in the cut: the card's lines are revealed over time and
            # the credit sits under them.
            out.append((cut, clock + length * 0.8))
        clock += length
    return out


def legible(at: float) -> str:
    import pytesseract
    from PIL import Image
    with tempfile.TemporaryDirectory() as work:
        png = Path(work) / "f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}",
                        "-i", str(FILM), "-frames:v", "1", str(png)],
                       check=True)
        return pytesseract.image_to_string(Image.open(png).convert("L"))


@pytest.fixture(scope="module")
def delivered():
    if not FILM.exists() or not PROPS.exists():
        pytest.skip("no delivered slice on this machine — "
                    "scripts/slice_check.py renders one")
    found = cards()
    if not found:
        pytest.skip("this slice carries no document_reveal cut")
    return found


class TestTheCreditIsOnTheFrame:
    def test_every_document_card_carries_a_credit_in_its_props(self, delivered):
        missing = [c["id"] for c, _ in delivered if not c.get("sourceLine")]
        assert missing == [], (
            f"these cards have nothing to print: {missing}")

    def test_every_document_card_draws_it(self, delivered):
        """THE PROOF. Read off the delivered picture, not off the props."""
        unread = []
        for cut, at in delivered:
            text = legible(at).lower()
            # The first distinctive word of the credit, which is enough:
            # OCR on a dark card loses punctuation, not words.
            wanted = [w for w in str(cut["sourceLine"]).split()
                      if len(w) > 3][:1]
            if not wanted:
                continue
            if wanted[0].lower() not in text:
                unread.append((cut["id"], cut["sourceLine"], at))
        assert unread == [], (
            f"the credit is in the props and not on the frame: {unread}")
