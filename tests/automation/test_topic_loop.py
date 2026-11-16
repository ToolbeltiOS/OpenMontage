"""The chain survives a topic with nothing disputed in it.

The angle gate can only run after research, so "this subject has no
disputed thread" is discovered around 20:00 on a Friday. The first version
of that gate blacklisted the entity and stopped the run, which spends a week
of the channel on a subject the gate was always going to refuse.

The loop lives at the RUNNER and not inside a stage: a stage knows about one
project and cannot choose a different subject, while the runner owns the
topic. Research runs, the gate answers, and on exit 3 the entity is
blacklisted and the next brief becomes the film — three topics at most.

HOW THIS IS REHEARSED
---------------------
By extracting the real block out of `scripts/run_weekly.sh` and running it
under bash with stubs for the stage, the gate and the notifier. Extracted
rather than retyped, so the thing under test is the text that will run on
Friday; a paraphrase would pass while the runner's own copy was broken.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_weekly.sh"


def extract() -> tuple[str, str]:
    """(the topic helpers, the research loop) out of the runner itself."""
    text = RUNNER.read_text()
    helpers_from = text.index("MAX_TOPICS_PER_RUN=3")
    helpers_to = text.index('if [[ -n "$RESUME" ]]; then', helpers_from)
    loop_from = text.index("TOPIC_TRY=1")
    # UP TO THE NEXT STAGE, not to the first `done`: the loop contains an
    # inner `while` that finds the next unblacklisted brief, so the first
    # `done` after the start is that one and the extraction came back with
    # the outer loop unclosed. Every rehearsal below then failed with
    # "unexpected end of file", which is the harness telling the truth —
    # but `test_the_block_was_found` passed anyway, because the text DID
    # end in `done`. It counts balance now.
    loop_to = text.index("pipeline_stage proposal", loop_from)
    return text[helpers_from:helpers_to], text[loop_from:loop_to].rstrip() + "\n"


HELPERS, LOOP = extract()


def rehearse(tmp_path: Path, briefs: list[str], codes: list[int],
             max_topics: str = "", blacklist: list[str] | None = None
             ) -> subprocess.CompletedProcess:
    """Run the real loop with a scripted sequence of gate exit codes."""
    repo = tmp_path / "repo"
    (repo / "artifacts").mkdir(parents=True)
    if blacklist:
        (repo / "artifacts" / "topic_blacklist.txt").write_text(
            "\n".join(blacklist) + "\n")
    (repo / "scripts").mkdir()
    brief_file = repo / "artifacts" / "topic_briefs.json"
    brief_file.write_text(json.dumps(
        {"briefs": [{"entity": e} for e in briefs]}))

    # The gate, as a stub that answers from a queue and records who asked.
    (repo / "scripts" / "check_channel_angle.py").write_text(
        "import sys, pathlib\n"
        f"codes = {codes!r}\n"
        "state = pathlib.Path(sys.argv[0]).with_name('calls.txt')\n"
        "seen = state.read_text().split() if state.exists() else []\n"
        "project = sys.argv[sys.argv.index('--project') + 1]\n"
        "state.write_text(' '.join(seen + [project]))\n"
        "i = len(seen)\n"
        "code = codes[i] if i < len(codes) else 0\n"
        "print(f'contested_claims: {0 if code == 3 else 9}')\n"
        "print(f'usable_disputed: {0 if code else 5}')\n"
        "sys.exit(code)\n")

    harness = tmp_path / "harness.sh"
    harness.write_text(f"""#!/bin/bash
set -uo pipefail
REPO="{repo}"
# ONE TOKEN. The runner calls "$PY" quoted, so a two-word value like
# "/usr/bin/env python3" is looked up as a single command and every call
# fails with "No such file or directory".
PY="{sys.executable}"
LOGDIR="{tmp_path}"
BRIEF="{brief_file}"
SMOKE=0
DRY_RUN=0
RESUME=""
TURNS_RESEARCH=10
say()    {{ printf 'SAY %s\\n' "$*"; }}
notify() {{ printf 'NOTIFY %s\\n' "$*"; }}
fail()   {{ printf 'FAIL %s | %s\\n' "$1" "$2"; exit 9; }}
pipeline_stage() {{ printf 'STAGE %s for %s\\n' "$1" "$SLUG"; }}

{HELPERS.replace('MAX_TOPICS_PER_RUN=3', max_topics or 'MAX_TOPICS_PER_RUN=3')}

TOPIC_INDEX=0
TOPIC="$(brief_entity 0)"
SLUG="$(slug_of "$TOPIC")"

{LOOP}

printf 'CHOSE %s\\n' "$SLUG"
""")
    harness.chmod(0o755)
    return subprocess.run(["/bin/bash", str(harness)],
                          capture_output=True, text=True, timeout=120)


class TestTheLoopIsTheRunnersOwn:
    def test_the_block_was_found(self):
        """If the extraction breaks, every test below passes on nothing."""
        assert "TOPIC_TRY=1" in LOOP
        assert "pipeline_stage research" in LOOP
        assert "topic_blacklist.txt" in LOOP
        assert LOOP.rstrip().endswith("done")
        assert "brief_entity()" in HELPERS and "slug_of()" in HELPERS
        # Balanced, or the block is a fragment and bash will not parse it.
        opens = len(re.findall(r"^\s*while ", LOOP, re.M))
        closes = len(re.findall(r"^\s*done\s*$", LOOP, re.M))
        assert opens == closes == 2, (opens, closes)


class TestATopicWithNoAngleIsReplaced:
    def test_the_second_topic_becomes_the_film(self, tmp_path):
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing", "Gamma Thing"],
                        codes=[3, 0])
        assert done.returncode == 0, done.stdout + done.stderr
        assert "CHOSE beta-thing" in done.stdout, done.stdout

    def test_the_research_stage_runs_again_for_the_new_topic(self, tmp_path):
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing"], codes=[3, 0])
        stages = re.findall(r"STAGE research for (\S+)", done.stdout)
        assert stages == ["alpha-thing", "beta-thing"], done.stdout

    def test_the_dropped_entity_is_blacklisted(self, tmp_path):
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing"], codes=[3, 0])
        black = (tmp_path / "repo" / "artifacts" / "topic_blacklist.txt")
        assert "Alpha Thing" in black.read_text()
        assert "Beta Thing" not in black.read_text()

    def test_every_attempt_is_logged_and_telegrammed(self, tmp_path):
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing"], codes=[3, 0])
        assert "SAY topic 2 of 3: Beta Thing" in done.stdout, done.stdout
        assert "NOTIFY" in done.stdout
        assert "Taking the next topic (2 of 3)" in done.stdout

    def test_a_brief_already_blacklisted_is_skipped(self, tmp_path):
        """Beta was refused in an earlier week, so the loop goes past it."""
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing", "Gamma Thing"],
                        codes=[3, 0], blacklist=["Beta Thing"])
        assert "is blacklisted as well — skipping" in done.stdout, done.stdout
        assert "CHOSE gamma-thing" in done.stdout
        stages = re.findall(r"STAGE research for (\S+)", done.stdout)
        assert stages == ["alpha-thing", "gamma-thing"], done.stdout


class TestItStopsRatherThanRunningForEver:
    def test_three_topics_is_the_most_it_tries(self, tmp_path):
        done = rehearse(tmp_path, ["A One", "B Two", "C Three", "D Four"],
                        codes=[3, 3, 3, 0])
        assert done.returncode == 9
        assert "no topic had an angle" in done.stdout
        stages = re.findall(r"STAGE research for (\S+)", done.stdout)
        assert len(stages) == 3, stages

    def test_an_exhausted_shortlist_stops_too(self, tmp_path):
        done = rehearse(tmp_path, ["Only One", "Only Two"], codes=[3, 3])
        assert done.returncode == 9
        assert "shortlist is" in done.stdout or "exhausted" in done.stdout

    def test_exit_one_is_not_a_topic_problem(self, tmp_path):
        """A brief that holds contested claims and names none of them is a
        stage that did not finish; the next topic cannot fix it."""
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing"], codes=[1, 0])
        assert done.returncode == 9
        assert "research (channel angle)" in done.stdout
        stages = re.findall(r"STAGE research for (\S+)", done.stdout)
        assert stages == ["alpha-thing"], done.stdout
        black = tmp_path / "repo" / "artifacts" / "topic_blacklist.txt"
        assert not black.exists(), "exit 1 must not blacklist the topic"

    def test_a_first_topic_that_passes_runs_once(self, tmp_path):
        done = rehearse(tmp_path, ["Alpha Thing", "Beta Thing"], codes=[0])
        assert done.returncode == 0
        assert "CHOSE alpha-thing" in done.stdout
        assert done.stdout.count("STAGE research") == 1
        assert "NOTIFY" not in done.stdout, "nothing to announce"
