"""A scene has to paint something. If it does not, the frame shows the floor.

WHAT THIS IS ABOUT
------------------
they-said-it-couldnt-be-built, published, has eight single-frame flashes —
luma 32 against neighbours at 15. Five of them are holes in the timeline and
are fixed by rounding both edges of a cut from the timeline. The other three
are not holes: 21332 is the first frame of c109, 32992 the first frame of
c169, 27668 the last frame of c141, and all three cuts cover those frames.

Extracted and looked at, all three show the same thing: the bare Layer 0
gradient with NO CHROME AT ALL — no act number, no scene index, no caption
furniture, no texture. That rules out an entrance envelope. `TextureField`
(c141, c169) paints `SYS.bg` on its root and always draws a `FrameLayer`;
`ImageScene` (c109) paints the theme background on its root and only fades
the `<Img>` inside it. A scene at opacity 0 would still show its own
backdrop and its own chrome. These frames show neither, so the scene subtree
was never painted — the same class as the `backgroundImage` race that
`useBackdrop` fixed, reached by a second path still being looked for.

WHAT THE TEST DEFENDS
---------------------
The remedy that does not depend on finding that path: nothing a viewer can
see should depend on Layer 0, because Layer 0 only ever shows on a frame
that already went wrong. Two halves, and this file holds both:

  * every scene the films dispatch paints an opaque floor of its own, so a
    frame that renders is never the background with a picture over it; and
  * the documentary's own floor is the house black, so a frame that does NOT
    render is near-black rather than a violet template gradient.

A source test, because the alternative is finding it in a delivered film:
the three frames above cost one publish and a scan of three finished films.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "remotion-composer" / "src"
EXPLAINER = (SRC / "Explainer.tsx").read_text()

#: Films whose props say which scenes actually have to hold up.
FILMS = ("they-said-it-couldnt-be-built", "easter-island", "noah", "king-tut")

#: A root that paints. `SceneShell` and `Plate` both paint `SYS.bg`
#: themselves, so delegating to either is painting.
FLOOR = re.compile(
    r"background(?:Color)?:\s*"
    r"(?:[A-Za-z_][\w.]*\.bg\b"          # SYS.bg, C.bg, tokens.bg
    r"|background\s*\?\?\s*[\w.]*bg\b"  # SceneShell's own root
    r"|\"#[0-9A-Fa-f]{3,8}\""              # a literal colour
    r"|backgroundColor\b"                  # the prop, defaulted opaque
    r"|theme\.\w*[Cc]olor\b)"
)
DELEGATES = re.compile(r"<SceneShell\b|<Plate\b")


def props_for(film: str):
    for root in ("OpenMontage", "runner", "fix-render-finalise", "asset-library"):
        path = (ROOT.parent / root / "projects" / film / "artifacts"
                / "render_props.json")
        if path.exists():
            return json.loads(path.read_text())["cuts"]
    return None


def dispatched() -> dict[str, str]:
    """cut type -> the component `SceneRenderer` returns for it."""
    out: dict[str, str] = {}
    for match in re.finditer(r'cut\.type === "([a-z_]+)"', EXPLAINER):
        tail = EXPLAINER[match.end():match.end() + 600]
        component = re.search(r"<([A-Z][A-Za-z]+)", tail)
        if component:
            out[match.group(1)] = component.group(1)
    return out


def source_of(component: str) -> str | None:
    """The component's OWN source, not the file it happens to live in.

    `ImageScene` is declared inside `Explainer.tsx` beside twenty others, so
    a check that reads the file answers about whichever component is first
    in it. The slice runs from the declaration to the next one at column 0.
    """
    for path in sorted(SRC.rglob("*.tsx")):
        text = path.read_text()
        start = re.search(rf"^(?:export )?const {component}\b", text, re.M)
        if not start:
            continue
        rest = text[start.end():]
        nxt = re.search(r"^(?:export )?(?:const|function) [A-Za-z]", rest, re.M)
        return rest[:nxt.start()] if nxt else rest
    return None


def used_types() -> set[str]:
    """Every cut type the four films actually used, plus the untyped path."""
    types: set[str] = set()
    for film in FILMS:
        cuts = props_for(film)
        if cuts is None:
            continue
        for cut in cuts:
            types.add(cut.get("type") or "__untyped__")
    return types


def paints_a_floor(source: str) -> bool:
    """Does the component's own root put something opaque under itself?

    Read from its first `return (` — what it computes above that cannot be
    on screen — and only as far as its root element's first children, so a
    background on some inner panel is not mistaken for a floor.
    """
    at = source.find("return (")
    head = source[at:at + 1200] if at >= 0 else source
    return bool(FLOOR.search(head) or DELEGATES.search(head))


SCENES = sorted(
    (cut_type, component)
    for cut_type, component in dispatched().items()
    if cut_type in used_types()
)


def test_the_films_dispatch_the_scenes_this_file_checks():
    """The control on the list itself. An empty list passes every test
    below it and measures nothing."""
    assert len(SCENES) >= 8, SCENES
    assert "texture_field" in dict(SCENES)


@pytest.mark.parametrize("cut_type,component", SCENES,
                         ids=[f"{t}->{c}" for t, c in SCENES])
def test_every_dispatched_scene_paints_its_own_floor(cut_type, component):
    source = source_of(component)
    assert source is not None, f"{component} is dispatched but has no source"
    assert paints_a_floor(source), (
        f"{component} ({cut_type}) does not paint a backdrop of its own, so "
        f"every frame of it is the composition's Layer 0 with a picture laid "
        f"over the top. Any moment the picture is absent — an entrance at "
        f"zero, a subtree that has not painted yet — shows the floor instead "
        f"of the cut.")


def test_the_untyped_image_path_paints_one_too():
    """63 of king-tut's 161 cuts and 93 of they-said-it's take this path:
    no `type`, a sourced photograph, `ImageScene`."""
    source = source_of("ImageScene")
    assert source is not None
    assert paints_a_floor(source)


def test_a_scene_with_a_bare_root_would_fail_this():
    """The control. Without it the check could be matching anything."""
    bare = '''
    export const Bare: React.FC = () => {
      return (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <Something />
        </AbsoluteFill>
      );
    };
    '''
    assert not paints_a_floor(bare)
    see_through = bare.replace('overflow: "hidden"', 'background: "transparent"')
    assert not paints_a_floor(see_through)


class TestTheDocumentaryStandsOnItsOwnBackground:
    """`resolveTheme` has no "wak3up-documentary" entry, so the films have
    always fallen through to `flat-motion-graphics` and taken its violet
    gradient as Layer 0. Nobody chose it; it is only ever seen on a frame
    that lost its picture."""

    def test_the_playbook_is_still_not_a_theme(self):
        """The reason this is needed at all. If someone adds the theme, the
        fall-through is gone and this file should be re-read, not deleted."""
        root = (SRC / "Root.tsx").read_text()
        themes = root[root.find("export const THEMES"):root.find("DEFAULT_THEME")]
        assert '"wak3up-documentary"' not in themes

    def test_a_documentary_floor_is_the_house_black(self):
        assert re.search(r"documentary\s*\?\s*SYS\.bg", EXPLAINER), (
            "the documentary's floor is not SYS.bg")

    def test_a_documentary_does_not_paint_the_template_gradient(self):
        assert re.search(r"documentary\s*\?\s*null\s*:\s*<AnimatedBackground",
                         EXPLAINER)

    def test_every_other_playbook_keeps_its_gradient(self):
        """Short-form templates are designed against it and have cards that
        deliberately render transparent over it."""
        assert "<AnimatedBackground theme={theme} />" in EXPLAINER

    def test_the_documentary_is_recognised_by_its_playbook(self):
        assert re.search(r'playbook\s*\n?\s*===\s*"wak3up-documentary"',
                         EXPLAINER)
