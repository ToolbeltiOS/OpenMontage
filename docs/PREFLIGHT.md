# What Friday needs before it starts

**BUILT 2026-11-10.** `run_weekly.sh --preflight`, run by
`launchd/com.wak3up.docs.preflight.plist` on Thursday 21:00, which checks
everything a run depends on and Telegrams a pass/fail WITHOUT picking a
topic, opening a model, taking the lock or rendering anything.

A preflight check earns its place by naming something that has actually
failed, or that would fail silently hours in.

## Two things the building of it measured

**1. `cmd | grep -q` under `set -o pipefail` reports a MATCH as a failure.**
`grep -q` exits on its first hit, the producer gets SIGPIPE, and pipefail
takes the pipeline's status from the producer. Measured, five runs of each:

    launchctl list | grep -q '<TAB>com.wak3up.docs.weekly$'        141, 141, 141, 141, 141
    launchctl list | grep -q '<TAB>com.wak3up.docs.afterpublish$'  0, 0, 0, 0, 0

Both agents were loaded. The difference is position: `weekly` is the FIRST
line of the output and `afterpublish` the last, so only the first cuts the
producer off mid-write. The first version of this preflight reported two
loaded agents as "not loaded" and a scheduled wake as absent. Checks capture
their output and match it in bash now, and
`tests/automation/test_preflight.py` refuses a `| grep -q` anywhere in the
script.

**2. StartCalendarInterval does not wake a sleeping Mac, and this one has no
wake set for any agent hour.** Measured with a throwaway agent:

  * While the Mac is awake it fires **3 to 5 seconds** after its minute,
    three firings out of three, and honours `WorkingDirectory` and
    `EnvironmentVariables`.
  * An agent that is **not loaded** at its scheduled time does **not** run
    when it is loaded afterwards — the firing is dropped, not deferred.
  * `pmset -g sched` on this machine lists exactly one repeating wake,
    `wakepoweron at 8:55AM Monday`, which belongs to something else. Nothing
    wakes it for Friday 19:00, Thursday 21:00, Tuesday 09:00 or Sunday 12:00.

What was NOT measured: a real sleep/wake cycle. Unloading an agent resets
launchd's record of it, so the second bullet is evidence about an unloaded
agent and not about a sleeping machine, and the documented behaviour for a
missed calendar job across sleep is that it runs on wake. Either way the
conclusion for Friday is the same: the run happens late or not at all.

## The policy, decided 2026-11-10

    sudo pmset -c sleep 0 displaysleep 10

**The Mac never sleeps on mains.** Not a `pmset repeat` wake per agent: one
setting covers every agent there will ever be, including ones not written
yet, and a machine that is simply awake cannot drop a firing at all. The
display still sleeps after ten minutes, which is the part nobody needs.

The preflight **asserts** it rather than trusting that it was run, reading
the `sleep` value from the **AC Power** section of `pmset -g custom`. The
battery section of this machine says `sleep 1`, so a parser that takes the
first `sleep` line it finds reads the wrong policy and passes a Mac that
sleeps a minute after the lid closes.

Being on battery and having AC sleep set to anything but 0 are the only two
failures that get a line **above** the table in the Thursday message rather
than a row inside it. Every other failure costs a stage; these two cost the
night, and 19.5 hours of run #2 went exactly that way.

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
