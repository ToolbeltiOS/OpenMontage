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
#: AN APPROVAL IS PER-FILM STATE, AND IT LIVES WITH THE FILM.
#:
#: It used to live in assets/library/illustrations/approved.json — one
#: tracked, shared file for every film ever made. Two things followed, and
#: both were measured on 2026-11-11 by approving a rehearsal's script:
#:
#:   1. `scripts/telegram_gate.py` posted EVERY illustration in the shared
#:      library, because `illustrations_for` reads the directory and filters
#:      by nothing. One "ok" on the Lighthouse rehearsal's script approved
#:      noah's "Ark under construction" and they-said-it's "Unworked blocks
#:      at Tiryns", recorded under the rehearsal's name. Approving a script
#:      silently approved other films' pictures, and there was no way to
#:      refuse one picture without refusing the script.
#:   2. Every approval dirtied a TRACKED file in the runner, which is a
#:      pull-only deploy target. `assets/` is not in the runner's dirty-code
#:      guard, so nothing complained; the next fast-forward would have.
#:
#: So approvals are written here, per film, in the film's own artifacts —
#: beside the revocation record that projects/noah/artifacts already holds.
APPROVALS = "illustration_approvals.json"

#: What the pictures are, and what made them. Shared, read-only, and the
#: only thing about illustrations that IS shared: a picture is a file in a
#: library, while permission to use it is a fact about one film.
MANIFEST = Path("assets/library/illustrations/manifest.json")


def approvals_path(project: str, root: Path | None = None) -> Path:
    return (root or Path(".")) / "projects" / project / "artifacts" / APPROVALS


def approvals(project: str, root: Path | None = None) -> dict:
    """This film's approval record, or an empty one."""
    import json

    path = approvals_path(project, root)
    if not path.exists():
        return {"project": project, "verdicts": []}
    return json.loads(path.read_text())


def verdicts(project: str, root: Path | None = None) -> list[dict]:
    """Every per-picture verdict, oldest first."""
    return list(approvals(project, root).get("verdicts") or [])


def approved_subjects(project: str, root: Path | None = None) -> set[str]:
    """Subjects whose LATEST verdict is ok.

    Only `verdicts` counts. projects/noah/artifacts/illustration_approvals.json
    records three illustrations approved at the 2026-10-31 script gate and
    then REVOKED, under `illustrations`, with the reasoning. That list is
    history and is deliberately not read here, so the revocation holds by
    construction rather than by a special case — which is the same argument
    the revocation itself makes about waivers.
    """
    latest: dict[str, str] = {}
    for row in verdicts(project, root):
        subject = row.get("subject")
        if subject:
            latest[subject] = row.get("verdict", "no")
    return {s for s, v in latest.items() if v == "ok"}


def record_verdicts(project: str, rows: list[dict], root: Path | None = None,
                    by: str = "the owner, by Telegram reply") -> Path:
    """Append per-picture verdicts to this film's record, with who and when.

    Appends rather than replaces: a second gate round is more evidence, not
    a correction, and `approved_subjects` takes the latest verdict per
    subject. Nothing here is ever written by hand — a verdict exists because
    somebody replied — which is the whole reason it can be trusted.
    """
    import datetime as dt
    import json

    path = approvals_path(project, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = approvals(project, root)
    blob.setdefault("project", project)
    blob.setdefault("verdicts", [])
    now = dt.datetime.now().isoformat(timespec="seconds")
    for row in rows:
        entry = dict(row)
        entry.setdefault("at", now)
        entry.setdefault("by", by)
        blob["verdicts"].append(entry)
    blob["note"] = (
        "Per-picture verdicts from the illustration gate, which runs after "
        "the edit stage has generated the pictures and before the render. "
        "One Telegram post per picture; a reply of no, or no reply by render "
        "time, demotes that cut to its fallback and the film renders anyway. "
        "Approvals are per FILM: a picture approved here is approved for "
        "this film and for nothing else.")
    path.write_text(json.dumps(blob, indent=1) + "\n")
    return path


def _identities(root: Path | None = None) -> list[set[str]]:
    """Every name that identifies one illustration.

    AN APPROVAL RECORDS THE TEXT THE OWNER WAS SHOWN, and that text changed.
    Until 2026-11-09 `subject` was the full descriptive line and the strip
    rendered it, badly: at 20px with 0.16em tracking a sixty-character line
    hit the strip's ellipsis, so the viewer read "a very large wooden vessel
    under construction on dry land, timber fra…". `subject` is a short
    on-screen label now and the full line lives in `prompt`, where it always
    also lived, and in `subject_was`.

    So an approval taken before the split names the long line and an
    approval taken after names the short one, and both are approvals of the
    same picture. Matching on any of a picture's names keeps a real approval
    valid across the rename. Rewriting the approval instead is not
    available: approvals are written by `record_approval` from a Telegram
    reply and never by hand, which is the whole reason they can be trusted.
    """
    import json

    path = (root or Path(".")) / MANIFEST
    if not path.exists():
        return []
    out = []
    for asset in json.loads(path.read_text()).get("assets", []):
        names = {asset.get(key) for key in ("subject", "subject_was", "prompt")}
        names.discard(None)
        names.discard("")
        if names:
            out.append(names)
    return out


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


def usable(subject: str, project: str,
           root: Path | None = None) -> tuple[bool, str]:
    """May this illustration be used in THIS film?"""
    ok = approved_subjects(project, root)
    if subject in ok:
        return True, "approved at the illustration gate"
    # The same picture under another of its names — see `_identities`.
    for names in _identities(root):
        if subject in names and names & ok:
            return True, ("approved at the illustration gate, under another "
                          "of the subject lines it was shown as")
    return False, ("not approved at the illustration gate — an illustration "
                   "is the one picture nobody sourced, so it is used only if "
                   "it was shown and approved for this film")


def demote_unapproved(cuts: list[dict], project: str,
                      root: Path | None = None) -> list[dict]:
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
        ok, why = usable(subject, project, root)
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
