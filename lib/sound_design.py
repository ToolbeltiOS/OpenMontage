"""The sound-design layer: ambience, room tone, risers, impacts, stings.

WHY IT IS A LAYER AND NOT A SET OF EDITS
----------------------------------------
Built here, in the stage that renders the audio, for the same reason the music
mix lives in `mix_audio` and not in a re-mux: a sound applied to a finished
render has an expiry date, and the date is the next re-render. This module
produces ONE wav the length of the film, and `mix_audio` sums it under the
voice with the same ducking envelope the music uses.

WHY THE LEVELS ARE OFFSETS
--------------------------
Every level is stated in the playbook as an offset from the music bed, not as
an absolute. The bed's own level has moved three times — -36 on run #1, -30 by
ear on an act-2 demo, -33 by ear on the whole film — and the floor has to move
with it, or the balance the owner approves at one setting is wrong at the next.

The offsets are applied in K-WEIGHTED LOUDNESS since 2026-10-25, because the
gate that checks them measures in it. See `_loudness`.

The references' beds sit 4 to 15 dB under the voice against our 20. Part of
what fills that distance on their films is not music — it is wind and room
tone. Raising the bed alone to close the gap would be a louder tune, which the
music criteria forbid. Building a floor underneath it is the thing being
copied.

WHAT IT WILL NOT DO
-------------------
It will not invent a sound. Every element names an asset with a provider, a
URL and a licence, and a spec that points at a file which is not on disk fails
rather than falling through to silence — a missing ambience that silently
becomes nothing is indistinguishable, in the mix report, from one that was
never asked for.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import numpy as np

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ───────────────────────────── helpers ───────────────────────────────────
def _read(path: str, want: int | None = None) -> np.ndarray:
    """Mono float32 at SR, decoded through ffmpeg so any input format works."""
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le",
           "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy()
    if want is not None:
        a = _fit(a, want)
    return a


def _fit(a: np.ndarray, n: int, crossfade_s: float = 8.0) -> np.ndarray:
    """Loop or trim `a` to exactly n samples, turning over rather than restarting.

    A hard loop point on a wind bed reads as the sound starting again, which is
    the one thing an ambience must never do. The same crossfade the music beds
    use is applied here.
    """
    if len(a) == 0:
        return np.zeros(n, dtype=np.float32)
    if len(a) >= n:
        return a[:n]
    xf = min(int(crossfade_s * SR), len(a) // 2)
    out = np.zeros(n, dtype=np.float32)
    pos, body = 0, len(a) - xf
    ramp = np.linspace(0.0, 1.0, xf, dtype=np.float32) if xf else None
    while pos < n:
        take = min(body, n - pos)
        out[pos:pos + take] += a[:take]
        pos += take
        if pos >= n or xf == 0:
            break
        tail = min(xf, n - pos)
        out[pos:pos + tail] += a[body:body + tail] * ramp[:tail][::-1]
        out[pos:pos + tail] += a[:tail] * ramp[:tail]
        pos += tail
    return out[:n]


def _rms_db(a: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12))


def _loudness(a: np.ndarray, peak: bool) -> float:
    """K-weighted loudness of an element, in LUFS.

    `peak` picks which figure: the loudest 400 ms window for a one-shot, the
    median window for something continuous.

    WHY NOT RMS, WHICH IS WHAT THIS USED TO BE.
    -------------------------------------------
    Because the gate that decides whether a sound is too loud measures
    K-weighted loudness, and these levels were being SET in broadband RMS. The
    two differ by several decibels depending on where an element sits in the
    spectrum, and the elements here are deliberately spread across it: this
    film's sting has a 59 Hz centroid, its impact 75 Hz, its sea ambience
    1,647 Hz. Measured on the curve at equal RMS, 30 Hz is 9.0 dB down on
    1 kHz and 1.6 kHz is 1.6 dB up. So an offset table in one unit and a
    ceiling in the other cannot be reconciled by anybody, and on the first
    run of the gate all fourteen one-shots came out over the bed while the
    table said three of them were under it.

    Measured in the same unit, the table means what it says.
    """
    _, st = short_term_of(a)
    live = st[st > -70.0]
    if not live.size:
        return -120.0
    return float(live.max() if peak else np.median(live))


def _to_level(a: np.ndarray, target_db: float, peak: bool = False) -> np.ndarray:
    """Scale to a target K-weighted loudness. Silence stays silence.

    `peak` is set for the one-shots, whose playbook keys are named
    `riser_peak`, `impact_peak` and `sting_peak`. Those names were a promise
    the code did not keep: it set the RMS of the WHOLE file, which for a
    transient with a long decay sits about 10 dB under its loudest moment. A
    key called `_peak` now refers to the peak.
    """
    cur = _loudness(a, peak)
    if cur < -110:
        return a
    return (a * (10 ** ((target_db - cur) / 20))).astype(np.float32)


#: How far above its own median a CONTINUOUS element may peak. An ambience is
#: a bed and the same argument applies to it as to a music bed: it is there to
#: be the room, and a bed that pokes 15 dB over its own middle is not a room,
#: it is an event. Measured on this film's assets: ambience_stone peaks 15.1 dB
#: over its median and ambience_sea 12.0 dB, which is why the floor read as a
#: layer of its own even at the quieter offsets.
#:
#: 3 dB, not the music bed's 6. The bed is allowed 6 LU of spread, so it can
#: sit 3 dB under its own median legitimately; an ambience peaking 6 dB over
#: ITS median would then be level with the music. At 3 dB the floor keeps 4 dB
#: of clearance against a bed at the bottom of its allowance, which is what
#: the gate measured it needing.
CONTINUOUS_CREST_MAX_DB = 3.0


#: How many times the crest is re-solved. One open-loop pass undershoots: the
#: gain curve is smoothed over 200 ms, which blunts the reduction at the
#: sharpest peak, and it is aligned to window centres while applied from
#: window starts. Measured, asking for 3 dB in one pass delivered 3.5 to
#: 6.9 dB across this film's five ambience beds — and the worst of them,
#: stone at 6.9, was the one that then failed the SFX gate by 1.2 dB.
#:
#: Iterating absorbs both effects without having to model either: each pass
#: re-measures and re-solves, so it converges in two or three.
#: Ten, and it should never be what stops the loop.
#:
#: The loop converges on the limit from above — each pass re-solves from the
#: measurement, and the 200 ms smoothing leaves the result a little over the
#: target every time — so a break on `crest <= limit` exactly is a break that
#: never fires, and every element burned all ten passes to land on 3.0 dB. The
#: cap was doing the stopping, which makes the cap load-bearing: an asset
#: slightly worse than this film's worst would have fallen out of the loop
#: still outside its limit.
#:
#: The break is on the same tolerance `inside_the_limit` reports against, so
#: the loop's own condition stops it and the cap is only there to bound a
#: pathological input. If the cap IS reached, the element is reported as
#: outside its limit and `build` refuses — rather than claiming a figure it
#: did not reach, which is the defect this whole function already had once.
HOLD_STILL_MAX_PASSES = 10

#: How close to the limit counts as inside it. One decimal, because that is
#: the precision the crest is reported to.
HOLD_STILL_TOLERANCE_DB = 0.1


def _hold_still(a: np.ndarray, limit_db: float = CONTINUOUS_CREST_MAX_DB
                ) -> tuple[np.ndarray, dict]:
    """Pull a continuous bed's loud moments down until it holds still.

    A feed-forward compressor computed from the MEASURED loudness curve, in
    the same idiom as the music ducking and for the same reason: a threshold
    compressor's depth depends on how far the signal is over the threshold, so
    it cannot be asked for "this bed peaks no more than 3 dB over its middle"
    and hold it. Here the crest is measured and the gain curve is solved to map
    it onto the limit, and then MEASURED AGAIN — because solving it once does
    not achieve it, and a function that reports a limit it did not reach is
    worse than one that reports the number it got.

    Only the part ABOVE the median is touched. A room getting momentarily
    quieter is not something a viewer notices; a room poking through the music
    is the whole complaint.
    """
    out = a
    crest_before = None
    passes = 0
    for _ in range(HOLD_STILL_MAX_PASSES):
        _, st = short_term_of(out)
        live = st[st > -70.0]
        if not live.size:
            break
        median = float(np.median(live))
        crest = float(live.max() - median)
        if crest_before is None:
            crest_before = crest
        if crest <= limit_db + HOLD_STILL_TOLERANCE_DB:
            break
        passes += 1

        k = 1.0 - limit_db / crest
        gain_db = np.where(st > median, -(st - median) * k, 0.0)
        # The curve is one value per 100 ms hop; stretch it to samples and
        # smooth it so the gain never steps.
        hop = max(1, len(out) // max(len(gain_db), 1))
        g = np.repeat(gain_db.astype(np.float32), hop)
        g = np.pad(g, (0, max(0, len(out) - len(g))), mode="edge")[:len(out)]
        # A boxcar by cumulative sum, not np.convolve: a direct convolution of
        # a 15-million-sample gain curve with a 9,600-tap kernel is 1.4e11
        # multiply-adds and took minutes per element. This is O(n).
        win = int(0.2 * SR)
        if win > 1:
            pad = win // 2
            c = np.cumsum(np.concatenate(
                ([0.0], np.pad(g.astype(np.float64), (pad, win - pad),
                               mode="edge"))))
            g = ((c[win:] - c[:-win]) / win)[:len(g)].astype(np.float32)
        out = (out * (10 ** (g / 20))).astype(np.float32)

    _, st2 = short_term_of(out)
    live2 = st2[st2 > -70.0]
    after = (round(float(live2.max() - np.median(live2)), 1) if live2.size
             else None)
    return out, {
        "crest_db": None if crest_before is None else round(crest_before, 1),
        "limit_db": limit_db,
        "held": passes > 0,
        "passes": passes,
        "crest_after_db": after,
        "inside_the_limit": (after is not None
                            and after <= limit_db + HOLD_STILL_TOLERANCE_DB),
        "passes_available": HOLD_STILL_MAX_PASSES,
    }


def short_term_of(a: np.ndarray):
    """The K-weighted short-term curve, from the gate that defines it."""
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from verify_sfx_level import short_term

    return short_term(a, SR)


def _ramp(n: int, shape: str) -> np.ndarray:
    t = np.linspace(0.0, 1.0, max(n, 1), dtype=np.float32)
    if shape == "in":
        return t ** 2
    if shape == "out":
        return (1.0 - t) ** 2
    return np.ones(n, dtype=np.float32)


# ───────────────────────────── building ──────────────────────────────────
def build(spec: dict[str, Any], total_seconds: float, music_bed_db: float,
          playbook: dict[str, Any], assets_dir: str,
          bed_curve: tuple[np.ndarray, np.ndarray] | None = None
          ) -> tuple[np.ndarray, dict]:
    """Render the whole sound-design layer, and report what went into it.

    `music_bed_db` is the music bed's K-weighted loudness as it sits in the
    film — the median of its short-term windows, which for a bed held inside
    6 LU is the level the bed is at. The CONTINUOUS elements are placed
    relative to it.

    `bed_curve` is that bed measured window by window, and when it is given
    the ONE-SHOTS are placed against the bed's level in their own moment
    instead of against its median. That is the literal reading of the rule —
    "everything below the bed's level in its moment" — and it is also the only
    version that works: measured on this film, the bed sits 3.2 to 5.0 dB
    below its own median at three of the six act boundaries, which is exactly
    where the stings are, so a sting placed 2 dB under the MEDIAN was 3 dB
    over the music actually under it.

    The level taken is the MINIMUM over the element's own window, not the mean
    of it, so the offset holds for every instant the element is audible rather
    than on average across it. The windows are 2 to 3 seconds and the bed
    moves about 1.5 dB inside one, so this costs very little and removes the
    whole question.

    Continuous elements deliberately do NOT follow the curve. An ambience that
    tracked the music would be a room that breathes with the score, which is a
    worse artefact than the one being fixed.
    """
    sd = playbook["audio"]["sound_design"]
    off = sd["levels_relative_to_music_bed_db"]
    n = int(total_seconds * SR)
    out = np.zeros(n, dtype=np.float32)
    used: list[dict] = []

    def asset_path(entry: dict) -> str:
        path = entry["path"]
        if not os.path.isabs(path):
            path = os.path.join(assets_dir, path)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"sound design asset missing: {path}. A spec that points at a "
                f"file which is not on disk fails here rather than becoming "
                f"silence — silence is indistinguishable from never asking.")
        return path

    # room tone, under the whole film
    if spec.get("room_tone"):
        rt = spec["room_tone"]
        held, crest = _hold_still(_read(asset_path(rt), n))
        a = _to_level(held, music_bed_db + off["room_tone"])
        out += a
        used.append({"element": "room_tone", **_prov(rt),
                     "crest": crest,
                     "level_db": round(music_bed_db + off["room_tone"], 1)})

    # one ambience per act, over that act's span
    for amb in spec.get("ambience", []):
        start = int(float(amb["start_seconds"]) * SR)
        end = min(int(float(amb["end_seconds"]) * SR), n)
        if end <= start:
            continue
        held, crest = _hold_still(_read(asset_path(amb), end - start))
        a = _to_level(held, music_bed_db + off["ambience"])
        fade = min(int(2.0 * SR), (end - start) // 4)
        if fade:
            a[:fade] *= _ramp(fade, "in")
            a[-fade:] *= _ramp(fade, "out")
        out[start:end] += a
        used.append({"element": "ambience", "act": amb.get("act"),
                     "palette": amb.get("palette"), **_prov(amb),
                     "crest": crest,
                     "level_db": round(music_bed_db + off["ambience"], 1)})

    # one-shots: risers into landings, impacts on reveal cuts, stings on acts
    def bed_under(lo: float, hi: float) -> float:
        """The bed's quietest short-term window between lo and hi seconds."""
        if bed_curve is None:
            return music_bed_db
        times, lufs = bed_curve
        sel = (times >= lo) & (times <= hi)
        if not sel.any():
            return music_bed_db
        live = lufs[sel]
        live = live[live > -70.0]
        return float(live.min()) if live.size else music_bed_db

    for kind, peak_key in (("risers", "riser_peak"),
                           ("impacts", "impact_peak"),
                           ("stings", "sting_peak")):
        for one in spec.get(kind, []):
            a = _read(asset_path(one))
            if kind == "risers":
                cap = int(sd["riser"]["max_seconds"] * SR)
                if len(a) > cap:
                    a = a[-cap:]            # keep the top of the riser, not its start
                a *= _ramp(len(a), "in")
                # a riser ENDS on the word it leads to
                at = int(float(one["at_seconds"]) * SR) - len(a)
            else:
                at = int(float(one["at_seconds"]) * SR)
            here = bed_under(at / SR, (at + len(a)) / SR)
            a = _to_level(a, here + off[peak_key], peak=True)
            lo = max(at, 0)
            hi = min(at + len(a), n)
            if hi > lo:
                out[lo:hi] += a[lo - at: hi - at]
            used.append({"element": kind[:-1], "at_seconds": one["at_seconds"],
                         **_prov(one),
                         "bed_here_db": round(here, 1),
                         "bed_median_db": round(music_bed_db, 1),
                         "level_db": round(here + off[peak_key], 1)})

    # A LIMIT THAT WAS NOT REACHED IS NOT A LIMIT.
    #
    # The crest control used to solve its gain curve once and report the figure
    # it was ASKED for. Asking for 3 dB delivered 3.5 to 6.9 dB across this
    # film's five ambience beds, and the worst of them then failed the SFX gate
    # by 1.2 dB — a gate catching the consequence of a claim made two modules
    # away. It iterates now, and if it still cannot get there the mix stops
    # here rather than at the gate.
    outside = [u for u in used
               if (u.get("crest") or {}).get("inside_the_limit") is False]
    if outside:
        raise SystemExit(
            "the sound-design layer was refused: these beds could not be held "
            "inside a " + f"{CONTINUOUS_CREST_MAX_DB} dB crest in "
            f"{HOLD_STILL_MAX_PASSES} passes:\n  - " + "\n  - ".join(
                f"{u['element']} {u.get('palette') or ''} ({u.get('path')}): "
                f"{u['crest']['crest_db']} dB -> "
                f"{u['crest']['crest_after_db']} dB. An ambience that peaks "
                f"this far over its own middle is an event, not a room; "
                f"choose a steadier recording."
                for u in outside))

    report = {
        "elements": used,
        "unit": "LUFS, K-weighted: peak 400 ms window for the one-shots, "
                "median window for ambience and room tone",
        "music_bed_db": round(music_bed_db, 1),
        "offsets_db": dict(off),
        "measured_db": round(_rms_db(out), 1),
        "peak_dbfs": round(float(20 * np.log10(np.max(np.abs(out)) + 1e-12)), 1),
        "seconds": round(total_seconds, 1),
    }
    return out, report


def _prov(entry: dict) -> dict:
    """Provenance travels with every sound, on the same terms as every picture."""
    return {
        "path": entry.get("path"),
        "provider": entry.get("provider"),
        "url": entry.get("url"),
        "licence": entry.get("licence"),
    }


def check_spec(spec: dict[str, Any], playbook: dict[str, Any]) -> list[str]:
    """Problems with a sound-design spec, before anything is rendered."""
    sd = playbook["audio"]["sound_design"]
    problems: list[str] = []

    def prov(entry: dict, where: str) -> None:
        for field in ("path", "provider", "url", "licence"):
            if not entry.get(field):
                problems.append(f"{where}: missing {field}")

    if not spec.get("room_tone"):
        problems.append(
            "no room tone. Written air with nothing under it reads as a "
            "dropout, and the viewer checks whether the audio broke")
    else:
        prov(spec["room_tone"], "room_tone")

    acts = {a.get("act") for a in spec.get("ambience", [])}
    for amb in spec.get("ambience", []):
        prov(amb, f"ambience[{amb.get('act')}]")
        if amb.get("palette") not in sd["ambience"]["palettes"]:
            problems.append(
                f"ambience[{amb.get('act')}]: palette {amb.get('palette')!r} is "
                f"not one of {sd['ambience']['palettes']}")
    if sd["ambience"]["per_act"] and len(acts) < 2:
        problems.append("ambience is per act; fewer than two acts carry one")

    per_act_impacts: dict[Any, int] = {}
    for imp in spec.get("impacts", []):
        prov(imp, f"impact@{imp.get('at_seconds')}")
        per_act_impacts[imp.get("act")] = per_act_impacts.get(imp.get("act"), 0) + 1
    for act, count in per_act_impacts.items():
        if count > sd["impact"]["max_per_act"]:
            problems.append(
                f"act {act}: {count} impacts, over the "
                f"{sd['impact']['max_per_act']} ceiling — three is a trailer")

    for r in spec.get("risers", []):
        prov(r, f"riser@{r.get('at_seconds')}")
        if float(r.get("seconds", 0)) > sd["riser"]["max_seconds"]:
            problems.append(
                f"riser@{r.get('at_seconds')}: {r.get('seconds')}s, over the "
                f"{sd['riser']['max_seconds']}s ceiling")

    for st in spec.get("stings", []):
        prov(st, f"sting@{st.get('at_seconds')}")

    return problems


def main(argv: list[str]) -> int:
    """Gate: validate a sound-design spec and prove every asset is on disk."""
    import yaml

    if len(argv) < 2:
        print("usage: sound_design.py <sound_design.json> [assets_dir]")
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        spec = json.load(fh)
    assets_dir = argv[2] if len(argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(argv[1]))),
        "assets", "audio", "sound_design")
    with open(os.path.join(ROOT, "styles", "wak3up-documentary.yaml"),
              encoding="utf-8") as fh:
        playbook = yaml.safe_load(fh)

    problems = check_spec(spec, playbook)

    # A spec that names a file which is not there renders as silence, and a
    # silent floor is indistinguishable in the mix report from one that was
    # never asked for. Check the disk here, not at render time.
    for group in ("ambience", "risers", "impacts", "stings"):
        for entry in spec.get(group, []):
            path = entry.get("path", "")
            full = path if os.path.isabs(path) else os.path.join(assets_dir, path)
            if not os.path.exists(full):
                problems.append(f"{group}: missing file {path}")
    rt = spec.get("room_tone") or {}
    if rt.get("path"):
        full = rt["path"] if os.path.isabs(rt["path"]) else os.path.join(assets_dir, rt["path"])
        if not os.path.exists(full):
            problems.append(f"room_tone: missing file {rt['path']}")

    counts = {g: len(spec.get(g, [])) for g in ("ambience", "risers", "impacts", "stings")}
    print("sound design:", ", ".join(f"{k} {v}" for k, v in counts.items()),
          f", room tone {'yes' if spec.get('room_tone') else 'NO'}")
    for p in problems:
        print("  -", p)
    print("SOUND DESIGN:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
