"""Does the type stay still?

WHY THIS CHECK EXISTS
---------------------
Text in the authored scenes shook. Two causes, neither of them visible in a
still:

  - the sustaining move — added so that a graphic held for fifteen seconds is
    not a frozen frame — carried the type with it, a fraction of a pixel per
    frame. A glyph moved by a fraction of a pixel is not moved, it is
    re-rasterised: the same stems land on different subpixels every frame and
    every edge crawls. Over a second the same move is several whole pixels, so
    the words also walk away from whatever they label.
  - the film look ran over the finished frame, so its per-frame grain and its
    chromatic offset landed on the glyph edges.

The second is a composite order and the renders enforce it — the type pass is
laid over the graded plate, so grain cannot be on top of it. This checks the
first, on the delivered file, in the only terms that matter: where the words
actually are.

THE RULE
--------
Find the text in a frame, and look at the same text one second later. It must
not have moved. A scene that means to move its text says so, and every
entrance in the film already does, in the props: this samples past the last
declared animation time in the cut.

HOW IT MEASURES, AND WHY NOT THE OBVIOUS WAY
--------------------------------------------
OCR finds the words; it does NOT judge whether they moved. Tesseract's boxes
are integers and they are not stable to a pixel: on two frames whose text
region is byte-for-byte identical it moved a box by 1px, because its layout
analysis reads the whole frame and the rest of the frame had changed.
Comparing boxes directly fails roughly one word in ten that way.

So the box says WHERE to look, and the shift is measured inside it by phase
correlation, which gives a sub-pixel answer from the glyph edges themselves.
That is both stricter and quieter than comparing integer boxes: measured on
this film, type that is bit-identical reads a median of 0.013px, and a
deliberate one-pixel shift reads 0.999px, with no overlap on any word.

    python3 lib/verify_type_lock.py <film.mp4> --cuts <props.json>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

#: Tesseract confidence below which a word is noise rather than a reading.
#: Real type on this film's frames comes back at 95-96.
MIN_CONFIDENCE = 70.0

#: A frame has to carry at least this many words to be worth comparing.
MIN_WORDS = 3

#: What counts as a word when reading a PLATE, where the question is whether
#: anything legible survived rather than where it is.
#:
#: Tesseract will read a word out of a texture. The film's background carries
#: a faint chevron moire, and on the plate pass it returned a single '<<' at
#: 74% confidence from a patch of it with nothing in it at all — which failed
#: the gate on a render that was correct. A character on its own is not
#: legible text; two characters with a letter or a digit among them is the
#: smallest thing that could be a word anyone missed, and every element that
#: WAS missed when the split was built read as a whole word at 95% or better.
MIN_PLATE_WORD_CHARS = 2

#: How far apart the two samples are taken, in seconds.
SAMPLE_GAP_S = 1.0

#: How far past the cut's last declared animation to take the first sample.
#: Every entrance in the film is declared in the props — a label's `at`, a
#: reveal's `at` plus its duration — so "unless the scene declares a text
#: move" is read from the scene rather than guessed at.
ENTRANCE_MARGIN_S = 0.8

#: Where to sample a cut that declares nothing.
DEFAULT_SETTLE_S = 2.0

#: How far a word may move in a second.
#:
#: Not zero, and the reason is worth writing down. The plate behind the type
#: is still moving — that is the whole design — and it is not smooth: the
#: background carries a faint texture, and that texture drifts about 0.5px a
#: second. A small word's box is mostly background, so in the dimmest boxes
#: the measurement reads the background rather than the glyph. Filtering by
#: contrast does not separate them and neither does a high-pass; trimming the
#: padding to 2px does, for most of them.
#:
#: Measured over every word in a text-heavy frame, against the same frame
#: shifted by exactly one pixel:
#:
#:     locked        median 0.013   p90 0.496   max 0.506
#:     shifted 1px   median 0.999   p10 0.945   min 0.865
#:
#: Every single word separates. 0.65 sits between the two, 1.3x clear on each
#: side. For scale: the move that caused the shake carried type about 3.7px a
#: second, so this catches it with more than five times the margin.
SHIFT_TOLERANCE_PX = 0.65

#: Padding around an OCR box before the patch is cut, in pixels. Small on
#: purpose — see above; at 6px the median measurement rose from 0.013 to 0.494
#: because the box filled up with moving background.
BOX_PAD_PX = 2

#: Patches smaller than this in either dimension are skipped: phase
#: correlation on a dozen pixels is noise.
MIN_PATCH_PX = 12


def frame_at(film: str, seconds: float, dest: Path) -> Path | None:
    """One frame, or None if the film has no frame there.

    ffmpeg exits 0 when a seek lands past the end: it simply writes nothing.
    The caller then opened a file that does not exist and died inside PIL with
    `FileNotFoundError` on a temp path — after the render, which is the worst
    possible moment to lose the gates. A sample past the end is now a skip
    with a name, not a traceback.
    """
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{seconds:.3f}", "-i", film,
         "-frames:v", "1", str(dest)], check=True)
    return dest if dest.exists() and dest.stat().st_size else None


def words(path: Path, min_confidence: float = MIN_CONFIDENCE) -> list[dict[str, Any]]:
    """Every word a reader can see, and the box it sits in."""
    import pytesseract
    from PIL import Image

    data = pytesseract.image_to_data(Image.open(path).convert("L"),
                                     output_type=pytesseract.Output.DICT)
    out = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if confidence < min_confidence:
            continue
        out.append({"text": text, "left": int(data["left"][i]),
                    "top": int(data["top"][i]), "width": int(data["width"][i]),
                    "height": int(data["height"][i]),
                    "confidence": round(confidence, 1)})
    return out


def declared_moves_until(cut: dict[str, Any]) -> float:
    """The last moment the cut declares something animating.

    Walks the cut for any `at` — a label's, a reveal's, a title's — rather
    than knowing the shape of every component. A reveal's duration counts
    towards its end.
    """
    latest = 0.0

    def walk(node: Any) -> None:
        nonlocal latest
        if isinstance(node, dict):
            at = node.get("at")
            if isinstance(at, (int, float)):
                latest = max(latest, float(at) + float(node.get("duration") or 0.0))
            for key, value in node.items():
                if key.endswith("_at") and isinstance(value, (int, float)):
                    latest = max(latest, float(value))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(cut)
    return latest


def shift_in_box(first, second, box: dict[str, Any]) -> tuple[float, float] | None:
    """How far the contents of one OCR box moved, to a fraction of a pixel."""
    import cv2
    import numpy as np

    h, w = first.shape[:2]
    x0 = max(0, box["left"] - BOX_PAD_PX)
    y0 = max(0, box["top"] - BOX_PAD_PX)
    x1 = min(w, box["left"] + box["width"] + BOX_PAD_PX)
    y1 = min(h, box["top"] + box["height"] + BOX_PAD_PX)
    if x1 - x0 < MIN_PATCH_PX or y1 - y0 < MIN_PATCH_PX:
        return None
    a = first[y0:y1, x0:x1].astype("float32")
    b = second[y0:y1, x0:x1].astype("float32")
    if a.std() < 1.0:
        return None                        # nothing in the box to correlate
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(a, b, window)
    return float(dx), float(dy)


#: How much of the cut list may fall past the end of the file before the
#: check is reporting on a different film from the one it was handed. One
#: frame at the very end is rounding; a tenth of the film is a truncated
#: render, and a check that skips it quietly PASSES, which is worse than
#: failing.
MAX_SKIPPED_FRACTION = 0.05


def _too_much_skipped(skipped: list[str], cuts: list[dict[str, Any]],
                      name: str) -> list[str]:
    if not cuts or len(skipped) <= max(1, int(len(cuts) * MAX_SKIPPED_FRACTION)):
        return []
    return [f"{len(skipped)} of {len(cuts)} cuts fall past the end of the "
            f"file, so {name} did not look at them — the film is shorter "
            f"than its own cut list (first: {skipped[0]})"]


def check(film: str, cuts: list[dict[str, Any]] | None = None,
          fps: float = 30.0) -> tuple[list[str], dict[str, Any]]:
    import cv2

    cuts = cuts or []
    problems: list[str] = []
    samples = []
    skipped: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for n, cut in enumerate(cuts):
            start = float(cut.get("in_seconds", 0.0))
            end = float(cut.get("out_seconds", 0.0))
            settle = max(DEFAULT_SETTLE_S,
                         declared_moves_until(cut) + ENTRANCE_MARGIN_S)
            if end - start < settle + SAMPLE_GAP_S + 0.1:
                continue                   # too short to hold still in
            t0 = start + settle
            first_png = frame_at(film, t0, tmpdir / f"a{n}.png")
            if first_png is None:
                skipped.append(cut.get("id"))
                continue                   # the film ends before this cut does
            boxes = words(first_png)
            # Our type, and only ours. The pictures in an archival film are
            # maps and documents covered in print, and on a cut authored to
            # push or pull that print MUST travel — c081's map moved 39px in
            # a second because the camera asked it to. Reading it as type
            # that drifted fails a film for obeying its own edit. A word the
            # cut put on screen, chrome included, is still measured, so the
            # move this gate exists for is still caught.
            ours = authored_words(cut, chrome=True)
            boxes = [b for b in boxes
                     if measurable(b["text"]) and _normalise(b["text"]) in ours]
            if len(boxes) < MIN_WORDS:
                continue                   # not a text-bearing scene
            second_png = frame_at(film, t0 + SAMPLE_GAP_S, tmpdir / f"b{n}.png")
            if second_png is None:
                skipped.append(cut.get("id"))
                continue
            first = cv2.imread(str(first_png), cv2.IMREAD_GRAYSCALE)
            second = cv2.imread(str(second_png), cv2.IMREAD_GRAYSCALE)

            moved = []
            sizes: list[float] = []
            measured_boxes = 0
            worst = 0.0
            for box in boxes:
                shift = shift_in_box(first, second, box)
                if shift is None:
                    continue
                measured_boxes += 1
                dx, dy = shift
                size = max(abs(dx), abs(dy))
                sizes.append(size)
                worst = max(worst, size)
                if size > SHIFT_TOLERANCE_PX:
                    moved.append((box, dx, dy))

            import numpy as np

            samples.append({
                "cut": cut.get("id"),
                "seconds": round(t0, 2),
                "settle_seconds": round(settle, 2),
                "words": len(boxes),
                "measured": measured_boxes,
                "moved": len(moved),
                "worst_shift_px": round(worst, 3),
                "median_shift_px": round(float(np.median(sizes)), 3) if sizes else 0.0,
                "declared": bool(cut.get("text_move")),
            })
            if moved and not cut.get("text_move"):
                shown = "; ".join(f"{b['text']!r} by {dx:+.2f},{dy:+.2f}px"
                                  for b, dx, dy in moved[:4])
                problems.append(
                    f"{cut.get('id')} at {t0:.1f}s: {len(moved)} of "
                    f"{measured_boxes} words move within a second, worst "
                    f"{worst:.2f}px — {shown}")

    problems += _too_much_skipped(skipped, cuts, "type lock")
    measured = {
        "scenes_sampled": len(samples),
        "scenes_with_movement": sum(1 for s in samples if s["moved"]),
        "worst_shift_px": round(max((s["worst_shift_px"] for s in samples),
                                    default=0.0), 3),
        "cuts_past_the_end": len(skipped),
        "samples": samples,
    }
    return problems, measured


#: Fields that name a FILE or an identifier rather than words on screen.
#: `source` is both, depending on the component — a credit line on a document
#: and a path on a sourced still — so it is read only when it is not a path.
NON_TEXT_KEYS = {
    "id", "src", "image", "backgroundImage", "backgroundVideo", "asset",
    "path", "act", "type", "transition_in", "transition_family", "beat",
    "register", "treatment", "asset_class", "camera", "status", "index",
}

#: Anything named `*_reason` explains a decision and is never painted.
#:
#: Not a tidy-up. `music_rise_reason` was added to cleared cuts and reads
#: "bed not rising here (-0.162 sd/s against a floor of 0.02)" — so 'of'
#: became a word the cut supposedly puts on screen, OCR read 'of' off an
#: 1886 map in that same cut, and plate purity failed a film that had not
#: changed a frame. A diagnostic that can fail a gate is worse than no
#: diagnostic, so the rule is on the NAME rather than a list that has to be
#: remembered every time one is added.
DIAGNOSTIC_SUFFIX = "_reason"

#: Chrome: the persistent frame's own words. They are NOT authored content —
#: plate purity must not count 'S 039' as an element someone forgot to tag,
#: because the frame paints it properly. But they ARE type, painted by us and
#: required to be still, so type lock measures them.
CHROME_KEYS = {"sceneIndex", "actNumber", "actTitle", "sourceLine"}


def _normalise(text: str) -> str:
    """A reading reduced to the letters and digits in it, lowercased."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def authored_words(cut: dict[str, Any], chrome: bool = False) -> set[str]:
    """Every word this cut asks to be PUT on screen, lowercased.

    Walks the cut for strings rather than knowing the shape of every
    component, the same way `declared_moves_until` walks it for times. Keys
    that carry a path or an identifier are skipped, so a filename never
    reads as a word someone wrote.
    """
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in NON_TEXT_KEYS or key == "reason" \
                        or key.endswith(DIAGNOSTIC_SUFFIX):
                    continue
                if key in CHROME_KEYS and not chrome:
                    continue
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            if node.startswith("/") or node.startswith("http"):
                return          # a path, not a line of type
            for raw in node.split():
                word = _normalise(raw)
                if word:
                    out.add(word)

    walk(cut)
    return out


#: The fewest alphanumeric characters a reading must have before its SHIFT is
#: worth believing.
#:
#: Not the same question as whether it is legible, which is what
#: MIN_PLATE_WORD_CHARS answers. This is about the measurement: the shift is
#: phase correlation inside the OCR box, and a box around one glyph is mostly
#: background — which the module header already records as the reason the
#: tolerance is not zero.
#:
#: Measured on the Easter Island delivery, on five cuts that failed on a
#: single '/' out of twenty to thirty-two words: the scene-index chrome that
#: '/' belongs to moved 0.004px over the same second, correlating at 0.95,
#: while the '/' box alone read 0.66 to 0.77px — straddling the 0.65
#: tolerance from below the noise floor rather than above it.
MIN_MEASURED_WORD_CHARS = 2


def measurable(text: str) -> bool:
    """Is this reading a big enough target to measure a shift in?"""
    return sum(ch.isalnum() for ch in text) >= MIN_MEASURED_WORD_CHARS


def plate_word_is_authored(text: str, cut: dict[str, Any]) -> bool:
    """Is this plate reading one of the words the cut asked for?

    The gate's premise is that anything legible in the plate is type that
    was missed. That holds for a film whose pictures are photographs. It
    does not hold for one built from archival maps and documents, where the
    PICTURE is covered in printed words: on the Easter Island film every one
    of the 32 readings was a place name engraved on a nineteenth-century
    map, or two characters out of grain, and not one was a missed element.

    Asking the cut settles it. A word the cut asked to be put on screen,
    found in the plate, is an element that did not get the type class —
    which is the defect this gate was written for, and still fails. A word
    the cut never mentions was in the photograph, and no amount of tagging
    will remove it.
    """
    word = _normalise(text)
    return bool(word) and word in authored_words(cut)


def plate_is_clean(plate: str, cuts: list[dict[str, Any]] | None = None
                   ) -> tuple[list[str], dict[str, Any]]:
    """Nothing readable survives into the plate pass.

    The split works by a class on every text element, and a text element that
    nobody marked is simply still there — it would be baked into the plate,
    take the grain on its edges, and drift with the plate under locked type
    saying the same words. That is exactly how the data strip was found, by
    eye, in the first plate render.

    So the plate is read. Anything legible in it is type that was missed.
    """
    cuts = cuts or []
    problems: list[str] = []
    found: list[dict[str, Any]] = []
    in_picture: list[dict[str, Any]] = []
    skipped: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for n, cut in enumerate(cuts):
            start = float(cut.get("in_seconds", 0.0))
            end = float(cut.get("out_seconds", 0.0))
            if end - start < 2.0:
                continue
            at = start + (end - start) / 2
            png = frame_at(plate, at, tmpdir / f"p{n}.png")
            if png is None:
                skipped.append(cut.get("id"))
                continue                   # the plate ends before this cut does
            for w in words(png):
                if len(w["text"]) < MIN_PLATE_WORD_CHARS:
                    continue
                if not any(ch.isalnum() for ch in w["text"]):
                    continue
                entry = {**w, "cut": cut.get("id"), "seconds": round(at, 2)}
                if plate_word_is_authored(w["text"], cut):
                    found.append(entry)
                else:
                    in_picture.append(entry)
    if found:
        shown = ", ".join(f"{w['text']!r} in {w['cut']}" for w in found[:6])
        problems.append(
            f"{len(found)} words are legible in the plate pass — they carry no "
            f"type class, so they will be graded and grained as picture and "
            f"will drift with the plate: {shown}")
    problems += _too_much_skipped(skipped, cuts, "plate purity")
    return problems, {"words_in_plate": len(found),
                      # Reported, never failed: words the pictures themselves
                      # carry. They are counted so the measurement stays
                      # beside the verdict — a film whose plate suddenly
                      # reads a hundred of these has changed, pass or not.
                      "words_in_picture": len(in_picture),
                      "picture_text": [
                          {"cut": w["cut"], "text": w["text"]}
                          for w in in_picture[:40]],
                      "cuts_past_the_end": len(skipped),
                      "found": found[:40]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("film")
    ap.add_argument("--cuts", required=True)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--plate", action="store_true",
                    help="read the film as a PLATE pass: it must contain no type")
    args = ap.parse_args()
    blob = json.loads(Path(args.cuts).read_text())
    cuts = blob["cuts"] if isinstance(blob, dict) else blob
    if args.plate:
        problems, measured = plate_is_clean(args.film, cuts)
        print(f"{measured['words_in_plate']} words legible in the plate pass")
        for p in problems:
            print("  -", p)
        print("PLATE PURITY:", "PASS" if not problems else "FAIL")
        return 0 if not problems else 1
    problems, measured = check(args.film, cuts, args.fps)
    print(f"{measured['scenes_sampled']} text-bearing scenes sampled a second "
          f"apart, {measured['scenes_with_movement']} with any word moving, "
          f"worst {measured['worst_shift_px']}px")
    for s in measured["samples"]:
        print(f"   {s['cut']} at {s['seconds']}s: {s['measured']} words, "
              f"worst {s['worst_shift_px']}px")
    for p in problems[:20]:
        print("  -", p)
    print("TYPE LOCK:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
