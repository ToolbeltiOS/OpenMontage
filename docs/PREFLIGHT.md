# What Friday needs before it starts

Collected during merge week for **item 9**: `run_weekly.sh --preflight`,
run by launchd on Thursday 21:00, which checks everything a run depends on
and Telegrams a pass/fail WITHOUT picking a topic or opening a model.

A preflight check earns its place by naming something that has actually
failed, or that would fail silently hours in.

## The list

| check | why it is here |
|---|---|
| branch is `automation` | the runner is pinned to it; a stray checkout renders the wrong code |
| code tree clean | `assert_code_clean` already refuses mid-run; knowing on Thursday is cheaper than losing a Friday |
| `remotion-composer/node_modules` is a real directory with a remotion binary | it was a SYMLINK into another worktree for four films (item 1). Already a start check in `run_weekly.sh`; preflight should say it on Thursday rather than at 19:00 Friday |
| power: on mains, battery healthy | 19.5 hours of run #2 were lost to a Mac asleep on battery |
| Telegram: BOTH bots answer | the gate bot and the notify bot are separate tokens; one working is not both working |
| YouTube OAuth token valid and refreshing | 6 months of disuse expires it; `scripts/check_youtube_auth.py` already measures this |
| Pixazo key present and inside the 600/month cap | a refusal mid-run wastes the stage that asked |
| disk ≥ 40 GB free | a film is ~12 GB of plate, look, type and delivery; a full disk fails at the mux |
| **`.venv-depth` exists and is Python ≥ 3.11** | **see below** |
| **Depth Anything V2 weights are in the HF cache** | **see below** |

## The 2.5D dependencies (added 2026-11-09, item 5)

`visual-quality` brings the 2.5D stills path. It is **not wired into
`run_weekly.sh`** — nothing in the weekly chain references
`build_25d_cuts`, `render_25d` or depth — so merging it does not put
Friday at risk today. It becomes a live failure the moment a stage authors
a `depth_clip` or someone wires the builder in, and it would fail at the
first `annotated_still` that needs one, hours into a run.

What it needs, and where:

  * **`<worktree>/.venv-depth/bin/python`, Python ≥ 3.11.** BUILT IN THE
    RUNNER 2026-11-09 from `requirements-depth.txt` (fully pinned, 76
    packages): depthflow 1.0.1 on Python 3.12.14. Rebuild with
    `uv venv --python 3.12 .venv-depth` then
    `uv pip install --python .venv-depth/bin/python -r requirements-depth.txt`. The path is
    WORKTREE-RELATIVE (`DEPTH_PY = ROOT / ".venv-depth" / "bin" / "python"`
    in `scripts/build_25d_cuts.py` and `lib/verify_depth_parallax.py`), so
    the dev tree having one does not help the runner. DepthFlow's renderer
    imports `typing.Self`, which 3.10 does not have, and the pipeline's own
    venv is 3.10 — hence a second interpreter rather than an upgrade.

    Was missing in `runner` until 2026-11-09, which meant the tree that
    makes the films could not build a 2.5D cut at all while the dev tree
    could.

  * **`depthflow`** in that interpreter, plus `imageio`, `numpy` and `PIL`,
    which `render_25d.py` and `anchor_track.py` import.

  * The DEPTH MAP itself needs none of that. `depth_cache` is imported
    in-process and runs under the pipeline's own 3.10 venv, which already
    carries torch 2.8.0 and transformers 4.57.6 — measured 2026-11-09. Only
    the DepthFlow clip and the anchor track need the second interpreter, so
    the gap was always narrower than "the 2.5D dependencies".

  * **Depth Anything V2 weights**: `depth-anything/Depth-Anything-V2-Small-hf`,
    about 95 MB. These live in `~/.cache/huggingface`, which is USER-level
    and therefore shared by every worktree — so this is not a per-tree
    problem, but it is still a preflight item: a cleared cache means a
    download mid-run, and a download mid-run is a surprise.

    Measured 2026-11-09: present.

The preflight check should be **conditional on use**: assert the depth
interpreter only when the pipeline can actually reach it, so a run that
authors no 2.5D cut is not blocked by a dependency it never touches.
