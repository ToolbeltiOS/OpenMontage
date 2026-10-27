# The $0 local Flux route: tried once, does not run on this machine

**Result: stopped. The machine swaps hard and no image was produced.**

## What was set up

| | |
|---|---|
| machine | Apple M1, **16 GB** unified memory, 8 cores, 135 GB disk free |
| ComfyUI | cloned and installed, own venv, **torch 2.14.1, MPS available** |
| checkpoint | `flux1-schnell-fp8.safetensors`, **16.05 GB** (17,236,328,572 bytes), downloaded intact |
| workflow | `tools/_comfyui/workflows/flux1-schnell-txt2img.json`, 1024², 4 steps, cfg 1.0 |
| prompt | the Pausanias-at-Tiryns test, from `lib/illustration_spec.py` |

## What happened

| measurement | value |
|---|---|
| time to first image | **none produced** in ~15 minutes (threshold was 5 min/image) |
| ComfyUI CPU at 6:08 elapsed | **0.0%** — not computing, waiting on page faults |
| ComfyUI resident set then | 5.0 GB, against a 16.05 GB checkpoint |
| swap in use during the run | **11,972 MB of 13,312 MB** |
| swap in use after killing it | **2,478 MB of 4,096 MB** |

The swap figure is the finding. Killing ComfyUI released about **9.5 GB of
swap**, so that much of the model was living on disk rather than in memory.
A 16.05 GB checkpoint cannot fit in 16 GB of unified memory alongside macOS,
and the process spent its time paging instead of sampling.

**One honest confound:** `mds_stores` — Spotlight — was at 99% CPU indexing
the 16 GB file that had just been downloaded, and would have slowed anything
running beside it. It does not explain the swap, which is structural: the
model is larger than the memory.

## What was not tried

- A **GGUF quantisation** (schnell Q4 is roughly 6.8 GB) would fit, at some
  cost in quality. It is not what was asked for and is not a free lunch, but
  it is the obvious next thing if the local route is wanted later.
- The 16.05 GB checkpoint is still on disk at
  `~/Developer/ComfyUI/models/checkpoints/`. It has not been deleted.

## Note on the workflow

`tools/_comfyui/workflows/flux2-txt2img.json` could not be used. It is
FLUX.2-dev in NVIDIA's **nvfp4** format with a Mistral-3-small text encoder,
and its `EmptyFlux2LatentImage` and `Flux2Scheduler` nodes are
FLUX.2-specific. Different architecture, and nvfp4 does not run on Apple
MPS. `flux1-schnell-txt2img.json` was written as the schnell equivalent.
