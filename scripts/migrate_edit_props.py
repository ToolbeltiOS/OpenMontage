#!/usr/bin/env python3
"""Bring a finished film's edit up to the props contract, by rule.

WHY A SCRIPT AND NOT A PAIR OF HANDS
------------------------------------
Films #5 and #6 are being re-rendered to replace what is published, and
their edits carry values the gates now refuse. Repairing those by hand —
or by a model reading each one and deciding — is how you get a film that
nobody can reproduce and a diff nobody can check. Every change here is a
RULE, applied uniformly, printed with its before and after.

WHAT IT CONVERTS, AND BY WHAT RULE
----------------------------------
1. A TIMELINE EVENT'S YEAR, where it is a string or a fraction.

   The strings are dates written for a reader: "27 Jul", "8 Aug, 17:00
   Moscow", "17-18 Aug", "May 1946", "12 Sep 1967", "1945". They are
   parsed as dates and nothing else: a leading day/month/year is taken and
   the rest of the line is ignored, a range takes its first day, and a
   bare day-month takes `--year`, which the operator states once per film
   and which is recorded in the report.

   A fraction (king-tut's 1922.84) is read as a position inside its year
   and converted to the month and day it stood for.

   A value that is NOT a date — "after", "condition", "—" — is not given
   one. Inventing a date for it would put a claim about time on screen
   that the edit deliberately did not make. It is placed one day after the
   last dated event in its own cut and marked `undated`, which the
   component reads as "print no year for this one".

2. A TIMELINE SPAN, where it is a pair of numbers, becomes a pair of
   dates — the same axis, said the same way as the events on it.

3. A FRACTIONAL DENSITY, which is an element count the edit wrote on a
   0-1 scale: 0.4 is four tenths of an ordinary field, so it becomes
   `round(0.4 * TextureField's own default)`, held inside the schema's
   range. `Math.round(0.4)` is zero elements, which is why four texture
   beats of every film from #1 to #6 drew nothing at all.

It does NOT touch basemaps or map extents: `scripts/resolve_basemaps.py`
owns those, and it runs after this.

    .venv/bin/python scripts/migrate_edit_props.py --project <slug> --year 1945
    .venv/bin/python scripts/migrate_edit_props.py --project <slug> --apply
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: `TextureField`'s own default element count, which is what a fraction is
#: a fraction OF. Read from the component so the two cannot disagree.
TEXTURE_FIELD = ROOT / "remotion-composer" / "src" / "scenes" / "TextureField.tsx"

MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
MONTHS.update({m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)})

#: en dash, em dash and hyphen all turn up in "17–18 Aug".
DASHES = "–—-"


def default_density() -> int:
    """`density = 60` out of TextureField.tsx, not a number typed here."""
    found = re.search(r"density\s*=\s*(\d+)", TEXTURE_FIELD.read_text())
    if not found:
        raise SystemExit(
            f"no default density in {TEXTURE_FIELD} — refusing rather than "
            f"inventing the scale a fraction is a fraction of.")
    return int(found.group(1))


def parse_year(value: Any, default_year: int | None) -> dict | None:
    """A date out of what the edit wrote, or None if it is not a date."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        year = int(value // 1) if value >= 0 else -int(abs(value) // 1)
        frac = abs(value - year)
        if frac < 1e-9:
            return {"year": year}
        month = min(12, int(frac * 12) + 1)
        day = min(31, int(round((frac * 12 - int(frac * 12)) * 31)) + 1)
        out = {"year": year, "month": month}
        if day > 1:
            out["day"] = day
        return out
    if not isinstance(value, str):
        return None

    text = value.strip()
    # Everything after a comma is time of day, place or qualifier:
    # "8 Aug, 17:00 Moscow", "14 Aug, night".
    text = text.split(",")[0].strip()
    # A range takes its first day: "17-18 Aug".
    for dash in DASHES:
        if dash in text:
            head, _, tail = text.partition(dash)
            if head.strip().isdigit():
                text = f"{head.strip()} {tail.strip().lstrip('0123456789 ')}"
            break
    text = text.strip()
    if not text:
        return None

    bare_year = re.fullmatch(r"(-?\d{1,4})\s*(BC|BCE|AD|CE)?", text, re.I)
    if bare_year:
        year = int(bare_year.group(1))
        era = (bare_year.group(2) or "").upper()
        return {"year": -abs(year) if era in ("BC", "BCE") else year}

    day_month_year = re.fullmatch(
        r"(\d{1,2})\s+([A-Za-z]+)\.?\s+(-?\d{1,4})", text)
    if day_month_year and day_month_year.group(2).lower() in MONTHS:
        return {"year": int(day_month_year.group(3)),
                "month": MONTHS[day_month_year.group(2).lower()],
                "day": int(day_month_year.group(1))}

    month_year = re.fullmatch(r"([A-Za-z]+)\.?\s+(-?\d{1,4})", text)
    if month_year and month_year.group(1).lower() in MONTHS:
        return {"year": int(month_year.group(2)),
                "month": MONTHS[month_year.group(1).lower()]}

    day_month = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\.?", text)
    if day_month and day_month.group(2).lower() in MONTHS:
        if default_year is None:
            raise SystemExit(
                f"{value!r} is a day and a month with no year, and no --year "
                f"was given. The year is the one thing this cannot read off "
                f"the edit, and guessing it would date the film by accident.")
        return {"year": default_year,
                "month": MONTHS[day_month.group(2).lower()],
                "day": int(day_month.group(1))}

    month_only = re.fullmatch(r"([A-Za-z]+)\.?", text)
    if month_only and month_only.group(1).lower() in MONTHS:
        if default_year is None:
            raise SystemExit(f"{value!r} is a month with no year, and no "
                             f"--year was given.")
        return {"year": default_year,
                "month": MONTHS[month_only.group(1).lower()]}
    return None


def one_day_after(date: dict) -> dict:
    """The next day, for placing a marker the edit did not date."""
    out = {"year": date["year"], "month": date.get("month", 12),
           "day": date.get("day", 28) + 1}
    if out["day"] > 28:
        out["day"] = 1
        out["month"] = out["month"] + 1
        if out["month"] > 12:
            out["month"] = 1
            out["year"] += 1
    return out


def props_of(cut: dict) -> dict:
    scene = cut.get("scene")
    return scene if isinstance(scene, dict) else cut


def migrate(cuts: list[dict], default_year: int | None,
            density_default: int) -> list[str]:
    notes: list[str] = []
    for cut in cuts:
        props = props_of(cut)
        kind = props.get("type") or cut.get("type")
        cid = cut.get("id") or "<no id>"

        if kind == "texture_field":
            density = props.get("density")
            if (isinstance(density, (int, float))
                    and not isinstance(density, bool)
                    and float(density) != int(density)):
                count = max(4, min(400, int(round(float(density)
                                                  * density_default))))
                notes.append(f"{cid} density: {density} -> {count} "
                             f"({density} of TextureField's own default "
                             f"{density_default}; Math.round({density}) is "
                             f"0 elements)")
                props["density"] = count

        if kind != "timeline":
            continue

        last_dated: dict | None = None
        for index, event in enumerate(props.get("events") or []):
            year = event.get("year")
            if isinstance(year, int) and not isinstance(year, bool):
                last_dated = {k: event[k] for k in ("year", "month", "day")
                              if k in event}
                continue
            date = parse_year(year, default_year)
            if date is None:
                if last_dated is None:
                    raise SystemExit(
                        f"{cid} event {index}: {year!r} is not a date and "
                        f"there is no dated event before it to place it "
                        f"after. This one needs a human.")
                date = one_day_after(last_dated)
                event["undated"] = True
                notes.append(
                    f"{cid} event {index}: {year!r} is not a date — placed "
                    f"after {last_dated} and marked undated, so the card "
                    f"prints no year for it. Label: "
                    f"{event.get('label', '')[:48]!r}")
            else:
                notes.append(f"{cid} event {index}: {year!r} -> {date}")
            event.pop("year", None)
            event.update(date)
            last_dated = date

        span = props.get("span")
        if isinstance(span, list) and len(span) == 2 \
                and not isinstance(span[0], dict):
            pair = [parse_year(x, default_year) for x in span]
            if all(pair):
                notes.append(f"{cid} span: {span} -> {pair}")
                props["span"] = pair
    return notes


def write_like(path: Path, blob: Any, original: str) -> None:
    """Write it back the way it was written, so the diff is the change."""
    for indent in (1, 2, 4):
        for ascii_only in (True, False):
            if (json.dumps(json.loads(original), indent=indent,
                           ensure_ascii=ascii_only) + "\n") == original:
                path.write_text(
                    json.dumps(blob, indent=indent, ensure_ascii=ascii_only)
                    + "\n", encoding="utf-8")
                return
    path.write_text(json.dumps(blob, indent=1, ensure_ascii=True) + "\n",
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--artifacts", default=None)
    ap.add_argument("--year", type=int, default=None,
                    help="the year a bare day-and-month belongs to. Stated "
                         "once per film and recorded in this report; the "
                         "script refuses rather than guessing it.")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    art = (Path(args.artifacts) if args.artifacts
           else ROOT / "projects" / args.project / "artifacts")
    path = art / "edit_decisions.json"
    if not path.exists():
        print(f"no edit at {path}")
        return 1
    raw = path.read_text(encoding="utf-8")
    ed = json.loads(raw)

    notes = migrate(ed.get("cuts") or [], args.year, default_density())
    print(f"{args.project}: {len(notes)} change(s)"
          + (f", bare dates read as {args.year}" if args.year else ""))
    for note in notes:
        print(f"  {note}")
    if not args.apply:
        print("  (nothing written — pass --apply)")
        return 0
    if notes:
        write_like(path, ed, raw)
        print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
