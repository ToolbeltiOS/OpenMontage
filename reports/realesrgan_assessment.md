# Real-ESRGAN: assessed and not adopted

Item 2 was to upscale any bank still under 2500px by 2× with Real-ESRGAN
ncnn-vulkan, never on text-bearing assets, recording original and upscaled
resolution and the model. The binary was checked on this Mac first, as
instructed. **The recommendation is not to adopt it**, for five measured
reasons.

## 1. The rule as written never fires

**0 of 325 banked images are under 2500px.** The bank rejects anything under
3000 at fetch time (`MIN_BANK_LONG_EDGE`) and the smallest it holds is 3020.

## 2. The small files are derived crops, and they are already at native resolution

121 of 272 derived stills are under 2500px, smallest 1608. That looked like
the real target — until the crop rectangles were read:

| derived | file | crop width in the parent | parent |
|---|---|---|---|
| wm_401695745_detail | 1744px | **1742** | 3872px |
| wm_65339280_extreme | 1608px | **1608** | 5360px |

The crop is taken at native resolution: 1742 source pixels become a 1744px
file. Nothing is being thrown away and there is nothing to recover. They are
small **by design** — `DETAIL_FRAC = 0.45` and `EXTREME_FRAC = 0.30` of the
long edge — and `lib/derived_shots.py` already floors them at
`MIN_CROP_PX = 1600`, with the comment "below this the crop upscales past
~1.2x and softens".

## 3. Lanczos is more faithful than Real-ESRGAN

Ground truth is a real bank picture at 2560×1440, halved to 1280×720 to
stand in for a small source, then taken back to 2560×1440 three ways and
compared to the truth it came from:

| method | PSNR | SSIM | sharpness |
|---|---|---|---|
| truth | — | — | 3067.0 |
| bicubic | 30.10 | 0.8873 | — |
| **lanczos** | **30.28** | **0.8935** | 2260.2 |
| real-esrgan | 29.07 | 0.8715 | 2772.1 |

Real-ESRGAN is **1.2 dB worse** and loses on SSIM. It does read sharper —
2772 against Lanczos's 2260, closer to the truth's 3067 — but that sharpness
is **invented**: it scores further from the original while looking crisper,
which is what a GAN upscaler does. In a documentary assembled from sourced
photographs, hallucinated detail in a historical image is a provenance
problem, not an improvement.

## 4. The binary silently corrupts its output on this Mac

Every failure below exits **0** and writes a file of exactly the right
dimensions.

| configuration | result |
|---|---|
| default `-j 1:2:2`, auto tile | tiles upscaled correctly, assembled in the **wrong positions** |
| `-t 1536` (single tile) | output is **entirely black**, mean 0, std 0 |
| `-t 512`, `-t 256` | scrambled |
| `-j 1:1:1` | correct once (corr +0.9241), corrupt on another input |

The corruption is deterministic per input — four consecutive attempts on one
file returned identical correlations of −0.0052. It is detectable: phase
correlation against a bicubic upscale of the same input reads +0.92 for a
real upscale and ~0.00 for a corrupted one, with nothing between. But every
single output would have to be verified, and a quarter of a documentary's
stills silently scrambled is the exact failure class this pipeline keeps
being bitten by.

## 5. Cost

About 2 minutes per image threaded, about 6 minutes single-threaded, for
1280×720 → 2560×1440 on this machine.

## What came out of it that is worth keeping

The investigation found a live defect unrelated to upscaling: `NEVER =
("text_bearing",)` in `scripts/build_25d_cuts.py` matches nothing, because
no stage sets that class. The classifier runs two CLIP contests (scale,
occupancy) and a luma split — vast, intimate, dense, empty, bright — and has
no notion of text. Meanwhile **c081 and c124 use an engraved map** ("EASTER
ISLAND POLITICAL", 4091×2930) and both are 2.5D-eligible, as is c005's 1786
French chart of the island. Running a depth model over engraved line work
and displacing it would bend a coastline and its lettering, which on a map
is a factual distortion rather than a look. That guard is being made real.

Item 4 (RIFE) was conditional on item 2 being easy. It was not.
