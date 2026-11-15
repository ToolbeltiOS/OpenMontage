"""The checkpoint the stage owed, written by the runner from the artifact.

WHY THIS EXISTS
---------------
Run #5, 2026-11-13, twice in one night, in both directions.

  1. THE CHECKPOINT THAT WAS NEVER WRITTEN. The scene_plan stage wrote a
     158-scene `scene_plan.json` at 20:56 — schema-valid, 0.0–1191.9s with
     no gaps, matching the approved script exactly — and hit its 40-turn cap
     at 20:57, one turn before it could checkpoint. The existing rule
     forgives a cap hit only when a `completed` checkpoint is already there,
     so it had nothing to read, and $5.83 of correct work was failed over
     bookkeeping. The checkpoint had to be written by hand.

  2. THE CHECKPOINT THAT WAS WRITTEN TOO EARLY. The assets stage wrote
     `checkpoint_assets.json` at 21:33 with status `completed` and then kept
     working for 33 more minutes until the wall cap killed it at 22:06:51.
     Its embedded `asset_manifest` is 31,885 bytes; the file on disk is
     52,801 bytes, written at 22:08:50 — two minutes AFTER the kill, by a
     child that outlived it. The rule forgave the overrun on the strength of
     a snapshot that was already 33 minutes stale.

Both are the same mistake: treating the checkpoint as the authority on
whether the work is done, when the ARTIFACT is the work. A checkpoint is
bookkeeping, and bookkeeping should never be the thing that cancels a film.

WHAT THIS DOES
--------------
After a stage ends — cap hit or not — the runner reconciles the two:

  artifact missing            -> FAIL. There is nothing to carry forward.
  artifact invalid            -> FAIL. The control. A stage that wrote
                                 rubbish must still fail; the whole value of
                                 "the artifact validates" is that invalid
                                 means invalid.
  no checkpoint, valid        -> WRITE it, warn, carry on.          (case 1)
  checkpoint stale            -> REWRITE it from the artifact's final
                                 bytes, warn, carry on.             (case 2)
  checkpoint matches          -> FRESH. Nothing to do.

Staleness is decided by a fingerprint — sha256 and byte count of the
artifact file — stamped into `metadata.artifact_fingerprints` when the
checkpoint is written. That is how "written only after the artifact stops
changing" is ENFORCED rather than asked for: a stage may still checkpoint
whenever it likes, but a checkpoint that does not match the artifact the
next stage will read does not survive this step.

WHAT IT WILL NOT DO
-------------------
It will not touch the `script` stage. That stage's checkpoint carries
`human_approved`, which is the owner's reply at the Telegram gate and
nothing else. A runner that can write it is the self-approval hole of
2026-11-12 reopened from the other side — a `--resume` then skips the human
gate on the strength of a checkpoint no human ever answered. `script` is
refused by name, and a test holds that.

It will not touch a checkpoint that says `awaiting_human` either: that stage
is at a gate, and a gate is not a bookkeeping problem.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

try:                                    # lib/ on sys.path, as the scripts do
    import checkpoint as C
except ImportError:                     # imported as the package `lib`
    from lib import checkpoint as C     # type: ignore[no-redef]

#: The one stage whose checkpoint is a human's answer, not a record of work.
NEVER_RECONCILED = ("script",)

#: Statuses this step is entitled to replace. `awaiting_human` is absent on
#: purpose, and so is anything unrecognised.
REPLACEABLE = ("completed", "in_progress", "failed")

FINGERPRINT_KEY = "artifact_fingerprints"


def fingerprint(path: Path) -> dict[str, Any]:
    """What the artifact was, byte for byte, when the checkpoint was written."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def recorded_fingerprints(checkpoint: dict) -> dict:
    meta = checkpoint.get("metadata")
    if not isinstance(meta, dict):
        return {}
    found = meta.get(FINGERPRINT_KEY)
    return found if isinstance(found, dict) else {}


def stamp_fingerprints(metadata: Optional[dict], artifact_paths: dict[str, Path]
                       ) -> dict:
    """`metadata` with a fingerprint for every artifact read off disk.

    The checkpoint schema is `additionalProperties: false`, and `metadata`
    is the one free-form object in it — so this is where the fingerprint
    lives, rather than in a new top-level key that would need a schema
    change to be legal.
    """
    out = dict(metadata or {})
    prints = dict(out.get(FINGERPRINT_KEY) or {})
    for name, path in artifact_paths.items():
        if path and Path(path).exists():
            prints[name] = fingerprint(Path(path))
    if prints:
        out[FINGERPRINT_KEY] = prints
    return out


def artifact_path(projects_dir: Path, project: str, name: str) -> Path:
    return Path(projects_dir) / project / "artifacts" / f"{name}.json"


def missing_outputs(projects_dir: Path, project: str, stage: str
                    ) -> list[str]:
    """Which of this stage's DECLARED outputs are not on disk, in order.

    A checkpoint means "the hand-off is complete". It was written on the
    strength of one file, so it could say complete about a stage that had
    left the render four files short.
    """
    proj = Path(projects_dir) / project
    short: list[str] = []
    for rel, kind in C.STAGE_OUTPUTS.get(stage, ()):
        path = proj / rel
        if kind == "dir":
            if not path.is_dir():
                short.append(f"{rel}/ — the directory is not there")
            elif not any(child.is_file() for child in path.iterdir()):
                short.append(f"{rel}/ — the directory is empty")
        elif not path.exists():
            short.append(rel)
        elif path.stat().st_size == 0:
            short.append(f"{rel} — 0 bytes")
    return short


def reconcile(projects_dir: Path, project: str, stage: str,
              ) -> tuple[int, str, list[str]]:
    """(exit code, verdict, lines to print).

    Exit 0 means the next stage may read this one's artifact. Exit 1 means
    the run must stop, and the lines say why in the words the run log wants.
    """
    projects_dir = Path(projects_dir)
    lines: list[str] = []

    if stage in NEVER_RECONCILED:
        return 1, "REFUSED", [
            f"{stage}: this stage's checkpoint carries human_approved, which "
            f"is the owner's reply at the gate and nothing else.",
            "A runner that writes it is the self-approval hole reopened. "
            "Nothing was touched."]

    name = C.CANONICAL_STAGE_ARTIFACTS.get(stage)
    if not name:
        return 1, "UNKNOWN STAGE", [
            f"{stage}: no canonical artifact is defined for it, so there is "
            f"nothing to validate. Nothing was touched."]

    path = artifact_path(projects_dir, project, name)
    if not path.exists():
        return 1, "MISSING", [
            f"{stage}: no artifact at {path}.",
            "There is nothing to carry forward — this is a failed stage."]

    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        return 1, "UNREADABLE", [
            f"{stage}: {path} cannot be read as JSON: {error}",
            "A half-written artifact is a failed stage."]

    try:
        C.validate_artifact(name, blob)
    except Exception as error:                        # noqa: BLE001
        first = str(error).strip().splitlines()[0][:400]
        return 1, "INVALID", [
            f"{stage}: {path.name} does not validate against its schema.",
            f"  {first}",
            "The artifact is the authority, so an invalid one still fails."]

    short = missing_outputs(projects_dir, project, stage)
    if short:
        owed = len(C.STAGE_OUTPUTS.get(stage, ()))
        return 1, "INCOMPLETE", [
            f"{stage}: {path.name} validates, but this stage owes {owed} "
            f"output(s) and {len(short)} of them are not on disk:",
            *[f"  missing: {m}" for m in short],
            "A checkpoint says the hand-off is complete, so it is not "
            "written until the hand-off is complete. The artifact that "
            "validates is not the same thing as the work being done."]

    now = fingerprint(path)
    existing = C.read_checkpoint(projects_dir, project, stage)

    if existing:
        status = existing.get("status")
        if status == "awaiting_human":
            return 1, "AWAITING HUMAN", [
                f"{stage}: its checkpoint says awaiting_human — that is a "
                f"gate, not bookkeeping. Nothing was touched."]
        if status not in REPLACEABLE:
            return 1, "UNRECOGNISED STATUS", [
                f"{stage}: its checkpoint says status={status!r}, which this "
                f"step does not know how to reconcile. Nothing was touched."]
        was = recorded_fingerprints(existing).get(name)
        if status == "completed" and was == now:
            return 0, "FRESH", [
                f"{stage}: its checkpoint matches {path.name} byte for byte "
                f"({now['bytes']} bytes). Nothing to do."]
        if status == "completed" and was:
            lines.append(
                f"{stage}: its checkpoint was written when {path.name} was "
                f"{was.get('bytes')} bytes; it is now {now['bytes']}. The "
                f"checkpoint was written MID-STAGE and is stale.")
        elif status == "completed":
            lines.append(
                f"{stage}: its checkpoint records no fingerprint, so whether "
                f"it matches {path.name} cannot be known.")
        else:
            lines.append(f"{stage}: its checkpoint says status={status!r}, "
                         f"but {path.name} validates.")
    else:
        lines.append(f"{stage}: no checkpoint, but {path.name} validates "
                     f"({now['bytes']} bytes).")

    metadata = stamp_fingerprints(
        (existing or {}).get("metadata"), {name: path})
    metadata["reconciled_by"] = "the runner, from the artifact on disk"
    try:
        written = _write(projects_dir, project, stage, name, blob, existing,
                         metadata)
    except Exception as error:                        # noqa: BLE001
        # EVERY RULE IN lib/checkpoint.py STILL APPLIES, and the loudest is
        # the pipeline order: a stage whose predecessors are not complete and
        # approved cannot be advanced. Writing scene_plan's checkpoint on a
        # film whose script was never approved would be a worse hole than the
        # one this closes, so the refusal is kept and REPORTED — not raised
        # into the run log as a traceback.
        #
        # Caught as Exception rather than CheckpointValidationError on
        # purpose: lib/checkpoint.py is reachable both as `checkpoint` and as
        # `lib.checkpoint`, which are two class objects for one file, so
        # catching the name would catch it only sometimes. See
        # tests/lib/test_lib_modules_import_alone.py for why both exist.
        return 1, "REFUSED BY THE CHECKPOINT RULES", [
            f"{stage}: {path.name} validates, but the checkpoint was "
            f"refused:",
            f"  {str(error).strip().splitlines()[0][:400]}",
            "Nothing was written."]
    lines.append(f"  -> wrote {written.name} from the artifact's final bytes")
    return 0, "WROTE" if not existing else "REWROTE", lines


def _write(projects_dir: Path, project: str, stage: str, name: str,
           blob: Any, existing: Optional[dict], metadata: dict) -> Path:
    return C.write_checkpoint(
        projects_dir, project, stage, "completed", {name: blob},
        pipeline_type=(existing or {}).get("pipeline_type"),
        style_playbook=(existing or {}).get("style_playbook"),
        human_approval_required=True,
        # NOT a human's approval: this stage has no human gate (`script` is
        # refused above). The flag is what lib/checkpoint.py requires of any
        # `completed` write under a manifest whose stages default to gated,
        # and the runner's own gate branch passes it the same way.
        human_approved=True,
        metadata=metadata)
