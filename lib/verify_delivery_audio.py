"""Is the mix actually in the delivered file?

WHY THIS CHECK EXISTS
---------------------
The act 2 demo shipped with an AAC stream that was digital silence from the
first sample to the last: every sample exactly 0.0, mean and peak both -91 dB,
the whole histogram in one bin. The three mixes had been built correctly and
written to disk beside it. Nothing ever put one of them into the picture,
because no stage was responsible for doing so — the demo was rendered by hand,
Remotion's composition carries no audio, and the mp4 took the renderer's empty
track.

A silent delivery is the easiest defect in the pipeline to miss: the file
plays, the picture is right, the duration is right, the stream is present and
even has a plausible bitrate. Only decoding it says anything.

THE RULES
---------
1. The delivered audio's mean level is above -40 dBFS. A real mix sits near
   -18; -40 is far below anything that could be the film and far above digital
   silence, so the threshold does not need to be argued about.
2. Its integrated loudness is within 1 dB of the mix the delivery claims to
   carry. That is what catches the subtler failure: the right length of the
   WRONG audio, or a mix quietly re-levelled by an encode.

Note that these are two different measurements and not interchangeable. Rule 1
is RMS dBFS, which is what "is there anything there" wants; rule 2 is
ITU-R BS.1770 integrated loudness in LUFS, which is what "is it the mix we
made" wants. Comparing one against the other would be a category error — they
differ by several dB on ordinary material.

    python3 lib/verify_delivery_audio.py <film.mp4> [--expected-lufs -16.4]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from typing import Any

#: Mean level below which the delivered audio is not a mix.
MIN_MEAN_DBFS = -40.0

#: How far the delivered loudness may sit from the mix it claims to carry.
LOUDNESS_TOLERANCE_DB = 1.0


def mean_dbfs(path: str) -> tuple[float, float]:
    """Mean and peak level of the delivered audio, in dBFS."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True).stderr
    mean = peak = None
    for line in out.splitlines():
        if "mean_volume:" in line:
            mean = float(line.split("mean_volume:")[1].split("dB")[0])
        elif "max_volume:" in line:
            peak = float(line.split("max_volume:")[1].split("dB")[0])
    if mean is None:
        raise RuntimeError(f"no audio level could be measured in {path}")
    return mean, (peak if peak is not None else mean)


def integrated_lufs(path: str) -> float:
    """ITU-R BS.1770 integrated loudness of the delivered audio."""
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", path, "-af", "loudnorm=print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True).stderr
    blob = out[out.rfind("{"):out.rfind("}") + 1]
    value = float(json.loads(blob)["input_i"])
    # Silence measures -inf, which is both true and unserialisable. -99 keeps
    # the report valid JSON and is still unmistakably not a mix.
    return value if math.isfinite(value) else -99.0


def has_audio(path: str) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout
    return bool(out.strip())


def check(film: str, expected_lufs: float | None = None
          ) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []

    if not has_audio(film):
        return ([f"{film} carries no audio stream at all"],
                {"has_audio": False})

    mean, peak = mean_dbfs(film)
    if mean <= MIN_MEAN_DBFS:
        problems.append(
            f"the delivered audio means {mean:.1f} dBFS, under the "
            f"{MIN_MEAN_DBFS:.0f} dBFS floor — "
            + ("it is digital silence; the mix was never muxed in"
               if mean < -80 else "this is not a mix"))

    lufs = integrated_lufs(film)
    delta = None
    if expected_lufs is not None:
        delta = lufs - expected_lufs
        if abs(delta) > LOUDNESS_TOLERANCE_DB:
            problems.append(
                f"the delivered audio measures {lufs:.2f} LUFS against the "
                f"mix's {expected_lufs:.2f} ({delta:+.2f} dB, tolerance "
                f"±{LOUDNESS_TOLERANCE_DB:.0f}) — this is not the mix it "
                f"claims to carry")

    measured = {
        "has_audio": True,
        "mean_dbfs": round(mean, 2),
        "peak_dbfs": round(peak, 2),
        "integrated_lufs": round(lufs, 2),
        "expected_lufs": expected_lufs,
        "loudness_delta_db": None if delta is None else round(delta, 2),
    }
    return problems, measured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("film")
    ap.add_argument("--expected-lufs", type=float, default=None,
                    help="integrated loudness of the mix this file should carry")
    args = ap.parse_args()
    problems, measured = check(args.film, args.expected_lufs)
    if not measured.get("has_audio"):
        print("no audio stream")
    else:
        print(f"mean {measured['mean_dbfs']} dBFS, peak {measured['peak_dbfs']} dBFS, "
              f"{measured['integrated_lufs']} LUFS"
              + (f" ({measured['loudness_delta_db']:+} dB against the mix)"
                 if measured["loudness_delta_db"] is not None else ""))
    for p in problems:
        print("  -", p)
    print("DELIVERY AUDIO:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
