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
an absolute. The bed's own level is about to be auditioned at three settings
(-36, -30, -28 LUFS) and the floor has to move with it, or the balance the
owner approves at one setting is wrong at the next.

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


def _to_level(a: np.ndarray, target_db: float) -> np.ndarray:
    """Scale to a target RMS. Silence stays silence."""
    cur = _rms_db(a)
    if cur < -110:
        return a
    return (a * (10 ** ((target_db - cur) / 20))).astype(np.float32)


def _ramp(n: int, shape: str) -> np.ndarray:
    t = np.linspace(0.0, 1.0, max(n, 1), dtype=np.float32)
    if shape == "in":
        return t ** 2
    if shape == "out":
        return (1.0 - t) ** 2
    return np.ones(n, dtype=np.float32)


# ───────────────────────────── building ──────────────────────────────────
def build(spec: dict[str, Any], total_seconds: float, music_bed_db: float,
          playbook: dict[str, Any], assets_dir: str) -> tuple[np.ndarray, dict]:
    """Render the whole sound-design layer, and report what went into it.

    `music_bed_db` is the measured RMS of the music bed as it sits under
    speech. Every element is placed relative to it.
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
        a = _to_level(_read(asset_path(rt), n), music_bed_db + off["room_tone"])
        out += a
        used.append({"element": "room_tone", **_prov(rt),
                     "level_db": round(music_bed_db + off["room_tone"], 1)})

    # one ambience per act, over that act's span
    for amb in spec.get("ambience", []):
        start = int(float(amb["start_seconds"]) * SR)
        end = min(int(float(amb["end_seconds"]) * SR), n)
        if end <= start:
            continue
        a = _to_level(_read(asset_path(amb), end - start),
                      music_bed_db + off["ambience"])
        fade = min(int(2.0 * SR), (end - start) // 4)
        if fade:
            a[:fade] *= _ramp(fade, "in")
            a[-fade:] *= _ramp(fade, "out")
        out[start:end] += a
        used.append({"element": "ambience", "act": amb.get("act"),
                     "palette": amb.get("palette"), **_prov(amb),
                     "level_db": round(music_bed_db + off["ambience"], 1)})

    # one-shots: risers into landings, impacts on reveal cuts, stings on acts
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
            a = _to_level(a, music_bed_db + off[peak_key])
            lo = max(at, 0)
            hi = min(at + len(a), n)
            if hi > lo:
                out[lo:hi] += a[lo - at: hi - at]
            used.append({"element": kind[:-1], "at_seconds": one["at_seconds"],
                         **_prov(one),
                         "level_db": round(music_bed_db + off[peak_key], 1)})

    report = {
        "elements": used,
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
