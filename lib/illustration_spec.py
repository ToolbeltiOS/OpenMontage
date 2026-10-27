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
