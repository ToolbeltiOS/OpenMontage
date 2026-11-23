"""A callout style the composer cannot draw must not reach a render.

THE BUG THIS HOLDS SHUT
-----------------------
On 2026-11-21 the Pearl Harbor render died at frame 16301 of 36705 — four
hours twenty-six minutes in — with

    TypeError: Cannot read properties of undefined (reading 'icon')
        at CalloutBox (bundle.js:2868:41)

Cut c083 carried `callout_type: "note"`. `CalloutBox` indexes
`TYPE_DEFAULTS[type]`, which defines four styles and not that one, so
`defaults` was undefined. `borderColor` and `backgroundColor` are always
supplied by the call site in Explainer.tsx, so `||` short-circuits past
them and `.icon` is the first property actually read — which is why the
message names `icon` and not `border`.

Two things made it expensive. The props interface declares
`callout_type?: "info" | "warning" | "tip" | "quote"`, which is a
COMPILE-TIME claim about data that arrives at runtime as JSON, so nothing
checked it. And the failure landed on the frame the cut STARTS at, 543s
into a 1223s film, so the render had to get most of the way through before
it could fail. c125 held the same value at 806s.

The fix is a gate at the props boundary, and the valid set is read out of
the component rather than restated — a restated copy is a copy that
drifts, and the drift is the bug.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import build_render_props as B                          # noqa: E402

#: The component's own file, and the two interfaces that restate its set.
COMPONENT = ROOT / "remotion-composer" / "src" / "components" / "CalloutBox.tsx"
CONSUMERS = (ROOT / "remotion-composer" / "src" / "Explainer.tsx",
             ROOT / "remotion-composer" / "src" / "TalkingHead.tsx")

#: The two cuts exactly as the film carried them.
C083 = {"id": "c083", "type": "callout", "callout_type": "note",
        "text": "This is not memory against memory.", "in_seconds": 543.367}
C125 = {"id": "c125", "type": "callout", "callout_type": "note",
        "text": "Three of these files are physical.", "in_seconds": 806.533}


class TestTheStyleMustExistInTheComponent:
    def test_the_cut_that_killed_the_render_is_refused(self):
        """THE CONTROL: c083 as it was, at the boundary instead of frame
        16301."""
        with pytest.raises(SystemExit) as refusal:
            B.check_callout_types([C083], [])
        assert "c083" in str(refusal.value)
        assert "note" in str(refusal.value)

    def test_the_second_one_is_caught_in_the_same_pass(self):
        """Both, or the next render dies at 806s instead of 543s."""
        with pytest.raises(SystemExit) as refusal:
            B.check_callout_types([C083, C125], [])
        assert "c083" in str(refusal.value) and "c125" in str(refusal.value)

    def test_the_message_says_what_is_allowed(self):
        with pytest.raises(SystemExit) as refusal:
            B.check_callout_types([C083], [])
        for style in ("info", "warning", "tip", "quote"):
            assert style in str(refusal.value)

    @pytest.mark.parametrize("style", ["info", "warning", "tip", "quote"])
    def test_every_style_the_component_defines_is_accepted(self, style):
        B.check_callout_types([{"id": "c001", "callout_type": style}], [])

    def test_no_style_at_all_is_accepted(self):
        """`type = "info"` is a default parameter, so absent is valid and
        must not be refused — refusing it would fail every other film."""
        B.check_callout_types([{"id": "c001", "type": "callout"}], [])
        B.check_callout_types([{"id": "c002", "callout_type": None}], [])

    def test_an_overlay_is_checked_too(self):
        """TalkingHead.tsx:142 passes `overlay.callout_type` into the same
        component, so the overlays list is the same hole."""
        with pytest.raises(SystemExit) as refusal:
            B.check_callout_types([], [dict(C083, id="ov01")])
        assert "overlay ov01" in str(refusal.value)


class TestTheSetComesFromTheComponent:
    def test_it_reads_the_four_the_component_defines(self):
        assert B.callout_types() == {"info", "warning", "tip", "quote"}

    def test_the_consumers_declare_the_same_set(self):
        """THE DRIFT TRIPWIRE, and the reason this is not a hand-kept list.

        Explainer.tsx and TalkingHead.tsx each restate the union in a props
        interface. If a style is added to the component and not to them —
        or to them and not the component — these fall out of step and the
        next out-of-set value is a four-hour render again.
        """
        defined = B.callout_types()
        for consumer in CONSUMERS:
            declared = re.search(r'callout_type\?:\s*([^;]+);',
                                 consumer.read_text())
            assert declared, f"no callout_type union in {consumer.name}"
            assert set(re.findall(r'"([^"]+)"', declared.group(1))) == defined, (
                f"{consumer.name} disagrees with {COMPONENT.name}")

    def test_an_unreadable_component_refuses_rather_than_passing(self, tmp_path):
        """"I cannot tell" must not read as "all of it is fine" — that
        equivalence is what let `note` through in the first place."""
        stub = tmp_path / "remotion-composer" / "src" / "components"
        stub.mkdir(parents=True)
        (stub / "CalloutBox.tsx").write_text("export const CalloutBox = 1;\n")
        with pytest.raises(SystemExit) as refusal:
            B.callout_types(str(tmp_path))
        assert "TYPE_DEFAULTS not found" in str(refusal.value)

    def test_a_missing_component_refuses_too(self, tmp_path):
        with pytest.raises(SystemExit) as refusal:
            B.callout_types(str(tmp_path))
        assert "cannot read" in str(refusal.value)


class TestTheGateIsWiredIntoTheBuild:
    def test_the_props_builder_calls_it_before_writing(self):
        """The function existing is not the fix; being called is.

        Anchored on the props dict rather than on a line number: the call
        has to come before `render_props.json` is written, because after it
        is written the render is the next thing to read it.
        """
        src = (ROOT / "lib" / "build_render_props.py").read_text()
        code = "\n".join(line for line in src.splitlines()
                         if not line.lstrip().startswith("#"))
        called = code.index("check_callout_types(ed[")
        written = code.index('"cuts": ed["cuts"]')
        assert called < written, "the gate runs after the props are built"
