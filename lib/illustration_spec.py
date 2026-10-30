#!/usr/bin/env python3
"""What an illustration may be, and where it may never go.

AN ILLUSTRATION IS NOT EVIDENCE, AND THE FILM HAS TO SAY SO
------------------------------------------------------------
Every other picture in this film was made by someone who was there, or of
something that exists. An illustration is made by a model from a sentence.
That is a legitimate thing to show -- a scene nobody photographed, a
reconstruction, a thing described in a text and never drawn -- and it is
only legitimate if the viewer is never in doubt about which kind of picture
they are looking at.

So three things hold at once:

  1. THE STYLE IS FIXED AND IS NOT PHOTOREALISM. An engraving reads as a
     made thing. A photoreal render of Pausanias at Tiryns is a forgery of a
     photograph that cannot exist.
  2. THE STRIP SAYS SO FOR THE WHOLE HOLD, not as a flash card at the top.
     A label that leaves before the shot does is a label the viewer can miss.
  3. IT IS FORBIDDEN WHERE THE PICTURE IS THE ARGUMENT. A slot tagged
     `evidence` or `stills_of_record` is making a claim about what something
     looks like, and an illustration there is the film inventing its own
     evidence.

The licence record marks it generated, with the model and the prompt, so
nobody downstream has to guess whether a frame was sourced or made.
"""
from __future__ import annotations

from pathlib import Path

#: The house style. Fixed, so illustrations across films read as one hand
#: rather than as whatever the prompt happened to say that week.
STYLE_PROMPT = (
    "nineteenth-century steel engraving, fine parallel hatching and "
    "cross-hatching, monochrome sepia ink on aged paper, archaeological "
    "plate illustration, precise draughtsmanship, even lighting, no colour "
    "wash, visible engraved line texture, plate border"
)

#: What it must not be. Photorealism is first because it is the failure that
#: matters: a photoreal image of an unphotographed scene is a claim that a
#: photograph exists.
NEGATIVE_PROMPT = (
    "photorealistic, photograph, photographic, realistic rendering, 3d "
    "render, cgi, digital painting, concept art, cinematic lighting, depth "
    "of field, bokeh, lens flare, colour photograph, oil painting, "
    "watercolour, anime, cartoon, modern clothing, text, watermark, "
    "signature, logo"
)

#: PROMPT-LEVEL NEGATION DOES NOT RELIABLY EXCLUDE A THING, and this is
#: worth knowing before anyone trusts NEGATIVE_PROMPT to keep something out.
#:
#: The sledge-teams test was rendered three times. Two of the three put a
#: WHEEL ON AN AXLE under the sledge -- including one whose prompt said "NO
#: WHEELS, no cart, no axle" and whose negative listed "wheel, wheels,
#: cart, wagon, axle". FLUX schnell has no negative-prompt input at all, so
#: Pixazo folds the negative into the prompt text, where naming a thing can
#: just as easily summon it.
#:
#: The practical rule: the negative is a nudge against a STYLE (photoreal,
#: colour, cartoon) and cannot be relied on to exclude an OBJECT. Where an
#: object would be a factual error -- and a wheel under a megalith is
#: exactly that, since the claim these films make is that it was moved
#: without one -- the render has to be looked at and rejected, not
#: prompted around.
NEGATION_IS_UNRELIABLE = True

#: Slot tags where an illustration is refused outright.
FORBIDDEN_TAGS = ("evidence", "stills_of_record")

#: What the data strip reads, for the whole hold.
STRIP_PREFIX = "ILLUSTRATION"


def strip_text(subject: str) -> str:
    return f"{STRIP_PREFIX} — {subject}"


def allowed(slot: dict) -> tuple[bool, str]:
    """May this slot hold an illustration?"""
    tags = set(slot.get("tags") or [])
    if slot.get("slot_type") in FORBIDDEN_TAGS:
        tags.add(slot["slot_type"])
    hit = tags & set(FORBIDDEN_TAGS)
    if hit:
        return False, (
            f"the slot is tagged {sorted(hit)[0]!r}: the picture there IS "
            f"the argument, and an illustration would be the film inventing "
            f"its own evidence")
    return True, "not an evidence slot"


def licence_record(subject: str, model: str, prompt: str,
                   seed: int | None = None) -> dict:
    """The provenance entry for a generated frame.

    GENERATED IS A PROVENANCE CLASS, not an absence of one. It records what
    made the picture and from what, so the question "was this sourced or
    made" is answered in the manifest rather than by looking at the frame.
    """
    return {
        "provider": "generated",
        "generated": True,
        "model": model,
        "prompt": prompt,
        "style_prompt": STYLE_PROMPT,
        "negative_prompt": NEGATIVE_PROMPT,
        "seed": seed,
        "subject": subject,
        "licence": "generated — not a sourced work; no third-party rights",
        "attribution": "",
        "url": "",
        "note": "An illustration. Not evidence, and never placed in a slot "
                "tagged " + " or ".join(FORBIDDEN_TAGS) + ".",
    }


def full_prompt(subject: str) -> str:
    return f"{subject}. {STYLE_PROMPT}"


# --------------------------------------------------------------------------
# APPROVAL
#
# An illustration is the one picture in the film nobody sourced, so it is
# the one picture that does not get in on the strength of the pipeline
# having produced it. It is shown at the script gate, with its subject, and
# it is used only if the person approved the gate AND actually saw it.
#
# THOSE ARE TWO CONDITIONS AND THE SECOND IS THE EASY ONE TO LOSE. An upload
# that fails leaves a gate that was approved and an illustration nobody
# looked at, and an "ok" covering a picture the viewer never saw is exactly
# the informed-consent failure the gate exists to prevent. So the record is
# written from what the gate CONFIRMED DELIVERED, not from the list it tried
# to send.
# --------------------------------------------------------------------------

#: Where the gate records what it showed and the person approved.
APPROVED = Path("assets/library/illustrations/approved.json")


def approved_record(root: Path | None = None) -> dict:
    path = (root or Path(".")) / APPROVED
    if not path.exists():
        return {"approved": []}
    import json

    return json.loads(path.read_text())


def record_approval(subjects: list[str], project: str, attempt: int,
                    root: Path | None = None) -> Path:
    """Write the subjects the gate delivered and the person approved."""
    import datetime as dt
    import json

    path = (root or Path(".")) / APPROVED
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = approved_record(root)
    seen = {a["subject"]: a for a in blob.get("approved", [])}
    for sub in subjects:
        seen[sub] = {"subject": sub, "project": project, "attempt": attempt,
                     "approved_at": dt.datetime.now().isoformat(
                         timespec="seconds")}
    blob["approved"] = sorted(seen.values(), key=lambda a: a["subject"])
    blob["note"] = ("Written by scripts/telegram_gate.py from the "
                    "illustrations it CONFIRMED DELIVERED and the person "
                    "then approved. An illustration that failed to upload "
                    "is not here, because the approval did not cover it.")
    path.write_text(json.dumps(blob, indent=1) + "\n")
    return path


def usable(subject: str, root: Path | None = None) -> tuple[bool, str]:
    """May this illustration be used in the film?"""
    ok = {a["subject"] for a in approved_record(root).get("approved", [])}
    if subject in ok:
        return True, "approved at the script gate"
    return False, (f"not approved at the script gate — an illustration is "
                   f"the one picture nobody sourced, so it is used only if "
                   f"it was shown and approved")


def demote_unapproved(cuts: list[dict], root: Path | None = None
                      ) -> list[dict]:
    """Turn every unapproved illustration cut back into its fallback.

    THE FALLBACK IS THE SLOT'S OWN, not a blank. A slot that asked for an
    illustration already describes something the film needs to show, so it
    goes back to whatever it would have been without one: a sourced still
    if the slot has a path, and an authored graphic otherwise. Dropping the
    cut entirely would leave a hole in the narration it was holding.
    """
    changed = []
    for cut in cuts:
        if cut.get("type") != "illustration":
            continue
        subject = cut.get("subject") or cut.get("title") or ""
        ok, why = usable(subject, root)
        if ok:
            continue
        fell_to = "still" if cut.get("source") else "text_card"
        cut["type"] = "annotated_still" if fell_to == "still" else "text_card"
        cut.pop("subject", None)
        cut["illustration_refused"] = why
        cut["illustration_fallback"] = fell_to
        changed.append({"cut": cut.get("id"), "subject": subject,
                        "fell_to": fell_to, "why": why})
    return changed
