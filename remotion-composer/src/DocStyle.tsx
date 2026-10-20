import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { ActTitleCard } from "./scenes/ActTitleCard";
import { TitleSequence } from "./scenes/TitleSequence";
import { BeforeAfter } from "./scenes/BeforeAfter";
import { EvidenceCard } from "./scenes/EvidenceCard";
import { ScaleComparison } from "./scenes/ScaleComparison";
import { DocCaption } from "./design/DocCaption";
import { SceneShell } from "./design/Scene";
import { Graded } from "./design/Frame";
import { SYS, TYPE, TRACK, SHADOW, LAYOUT, GRADE, EXPO_OUT, EXPO_IN_OUT } from "./design/system";
import type { WordCaption } from "./components/CaptionOverlay";

/* ─────────────────────── the three new scene types ──────────────────────── */

/**
 * Act boundary. Title and epigraph are the act's own words — the epigraph is a
 * line from the approved act 2 narration, not a new piece of copy.
 */
export const DemoActTitleCard: React.FC = () => (
  <ActTitleCard
    act="ACT II"
    title="The statues that walked and the stone that sailed"
    epigraph="Whatever the method was, it failed often enough to leave a trail."
    image={staticFile("doc/aswan_quarry.jpg")}
  />
);

/**
 * The film's title card, as it sits after the cold open. The sting lands at
 * 1.8s; the audio stage places the hit on the same number.
 */
export const DemoTitleSequence: React.FC = () => (
  <TitleSequence
    title="They Said It Couldn't Be Built"
    kicker="A WAK3UPSOCIETY FILM"
    channel="WAK3UPSOCIETY"
    image={staticFile("doc/outro_hero.jpg")}
    sting_at={1.8}
  />
);

/**
 * Two framings of one plate: the Aswan quarry floor, and the dolerite pounder
 * sitting in the hollow it made.
 *
 * It is deliberately NOT a then-now pair. The component's first use is
 * restoration and then-now beats, and that needs two plates of one place in
 * two eras from one angle — matched material the asset bank does not hold yet.
 * Demonstrating it with a fabricated "archival" treatment of a modern photo
 * would be the one thing the playbook's quality gate forbids, so the demo
 * shows the other legitimate use — the repo's own two-framings-of-one-parent
 * rule — until the bank has a real pair.
 */
export const DemoBeforeAfter: React.FC = () => (
  <BeforeAfter
    before={staticFile("doc/aswan_quarry.jpg")}
    after={staticFile("doc/aswan_pounder_detail.jpg")}
    before_label="Plate"
    after_label="Detail"
    mode="wipe"
    at={0.7}
    wipe_seconds={2.4}
    rest={0.58}
    title="One tool, left where it stopped"
    caption="Unfinished obelisk quarry, Aswan — the dolerite pounder in its own hollow"
    actNumber="03"
    actTitle="The hole in the granite"
    sceneIndex="S 118 / ASWAN"
    source="Wikimedia Commons, CC BY-SA 4.0"
  />
);

/**
 * The same plate under three act grades, so the per-act offsets can be judged
 * side by side rather than described. Act 2 is the coolest and flattest, act 3
 * the warmest, act 4 the most lifted.
 */
export const DemoActGrades: React.FC = () => (
  <AbsoluteFill style={{ flexDirection: "row", background: SYS.bg }}>
    {(["act2", "act3", "act4"] as const).map((act) => (
      <div key={act} style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <Graded act={act}>
          <Img
            // the hero plate rather than the joint: the offsets are deliberately
            // small, and on a grey stone face they are invisible even when they
            // are working
            src={staticFile("doc/outro_hero.jpg")}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </Graded>
        <div
          style={{
            position: "absolute", left: 24, bottom: 24,
            fontFamily: SYS.label, fontSize: TYPE.labelSm, letterSpacing: TRACK,
            color: SYS.text, textShadow: SHADOW, opacity: 0.85,
          }}
        >
          {act.toUpperCase()}
        </div>
      </div>
    ))}
  </AbsoluteFill>
);

/** The citation beat, bound to ledger entry c38. */
export const DemoEvidenceCard: React.FC = () => (
  <EvidenceCard
    index="c38"
    claim="A void at least 30 metres long sits above the Grand Gallery."
    attribution="Morishima et al., Nature 552, 386–390 (2017)"
    detail="Detected independently with three muon technologies: nuclear emulsion films, scintillator hodoscopes, and gas detectors outside the pyramid."
    status="peer_reviewed"
    actNumber="04"
    actTitle="The cases nobody has closed"
    sceneIndex="S 159 / GIZA"
    caption="The first major inner structure found since the nineteenth century"
    source="DOI 10.1038/nature24647"
  />
);

/**
 * Comparative magnitude, bound to ledger entries c30 and c37.
 *
 * The unfinished quarry moai is deliberately absent: c37's narration note says
 * its mass is disputed (145–165 t in the encyclopedia against 270 t on
 * commercial sites) and must not be stated. The footnote says so on screen
 * rather than quietly dropping it.
 */
export const DemoScaleComparison: React.FC = () => (
  <ScaleComparison
    kicker="Scale"
    title="What was actually lifted"
    unit="tonnes"
    at={0.5}
    items={[
      { label: "Pumapunku, largest block", value: 131, note: "estimated" },
      { label: "Ahu Tongariki moai", value: 86, note: "heaviest ever erected", hero: true },
      { label: "Paro", value: 82, note: "tallest erected — 9.8 m" },
    ]}
    footnote="An unfinished figure still in the quarry is larger again; published masses disagree, so no figure is given for it."
    actNumber="02"
    actTitle="The statues that walked"
    sceneIndex="S 069 / RANO RARAKU"
    caption="Erected masses are solid; quarry estimates are not"
    source="Ledger c30, c37"
  />
);

/* ──────────────────────── the caption restyle frame ─────────────────────── */

const CAPTION_WORDS: WordCaption[] = (() => {
  const line =
    "Between the two there are roads — and lying beside those roads there are statues.";
  const words = line.split(" ");
  const per = 420; // ms per word, roughly the measured narration rate
  return words.map((w, i) => ({
    word: w,
    startMs: 200 + i * per,
    endMs: 200 + (i + 1) * per,
    pageBreakAfter: w.endsWith("—"),
  }));
})();

/**
 * The narration subtitle, over a graded still with the full persistent frame.
 * This is the frame to judge the caption restyle on: whether the type sits
 * under the image instead of on top of it.
 */
export const DemoDocCaption: React.FC = () => (
  <SceneShell
    actNumber="04"
    actTitle="The cases nobody has closed"
    sceneIndex="S 171 / SACSAYHUAMÁN"
    coords="13.5095° S  71.9817° W"
    caption="Sacsayhuamán, Cusco"
    source="Diego Delso · CC BY-SA 4.0"
  >
    <AbsoluteFill>
      <Graded>
        <Img
          src={staticFile("doc/sacsay_joint.jpg")}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </Graded>
    </AbsoluteFill>
    <DocCaption words={CAPTION_WORDS} />
  </SceneShell>
);

/* ───────────────────────────── the system sheet ─────────────────────────── */

const Swatch: React.FC<{ name: string; hex: string }> = ({ name, hex }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
    <div style={{ width: 54, height: 54, background: hex, border: `1px solid ${SYS.rule}` }} />
    <div>
      <div
        style={{
          fontFamily: SYS.label,
          fontSize: TYPE.labelSm - 4,
          letterSpacing: TRACK,
          textTransform: "uppercase",
          color: SYS.text,
        }}
      >
        {name}
      </div>
      <div style={{ fontFamily: SYS.data, fontSize: TYPE.dataSm - 4, color: SYS.faint }}>{hex}</div>
    </div>
  </div>
);

const Row: React.FC<{ k: string; v: string }> = ({ k, v }) => (
  <div
    style={{
      display: "flex",
      gap: 24,
      padding: "11px 0",
      borderBottom: `1px solid ${SYS.rule}`,
      alignItems: "baseline",
    }}
  >
    <span
      style={{
        width: 240,
        flexShrink: 0,
        fontFamily: SYS.label,
        fontSize: TYPE.labelSm - 5,
        letterSpacing: TRACK,
        textTransform: "uppercase",
        color: SYS.muted,
      }}
    >
      {k}
    </span>
    <span style={{ fontFamily: SYS.data, fontSize: TYPE.dataSm - 2, color: SYS.text }}>{v}</span>
  </div>
);

/**
 * Not a scene — the specification sheet. Four type levels, the palette, the
 * locked motion language and the grade, on one frame, so the look can be
 * approved as a system and not just as eight pictures.
 */
export const DocStyleSheet: React.FC = () => (
  <SceneShell
    actNumber="SYS"
    actTitle="wak3up-documentary"
    sceneIndex="DESIGN SYSTEM"
    coords={`grain ${GRADE.grainOpacity} · vignette ${GRADE.vignette}`}
    chrome
  >
    <div
      style={{
        position: "absolute",
        left: LAYOUT.left + 30,
        right: LAYOUT.left + 30,
        top: LAYOUT.top + 76,
        display: "flex",
        gap: 76,
      }}
    >
      {/* left: the four type levels, at their real sizes */}
      <div style={{ flex: 1.15 }}>
        <div
          style={{
            fontFamily: SYS.label,
            fontSize: TYPE.labelSm - 5,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            color: SYS.accent,
            marginBottom: 26,
          }}
        >
          Four levels, and nothing else
        </div>

        <div style={{ fontFamily: SYS.display, fontSize: TYPE.displaySm, color: SYS.text, lineHeight: 1.1 }}>
          Display — Source Serif
        </div>
        <div style={{ fontFamily: SYS.data, fontSize: TYPE.dataSm - 4, color: SYS.faint, marginTop: 6 }}>
          {`serif 600 · ${TYPE.displayXL}/${TYPE.display}/${TYPE.displaySm} px · titles and claims only`}
        </div>

        <div
          style={{
            fontFamily: SYS.label,
            fontSize: TYPE.label,
            fontWeight: 500,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            color: SYS.text,
            marginTop: 34,
          }}
        >
          Label — Inter caps
        </div>
        <div style={{ fontFamily: SYS.data, fontSize: TYPE.dataSm - 4, color: SYS.faint, marginTop: 6 }}>
          {`sans 500 · ${TYPE.label}/${TYPE.labelSm} px · ${TRACK} tracking · annotations, kickers`}
        </div>

        <div
          style={{
            fontFamily: SYS.data,
            fontSize: TYPE.data,
            color: SYS.text,
            marginTop: 34,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          Data — 131 t · 29.9792° N
        </div>
        <div style={{ fontFamily: SYS.data, fontSize: TYPE.dataSm - 4, color: SYS.faint, marginTop: 6 }}>
          {`mono 400 · ${TYPE.data}/${TYPE.dataSm} px · tabular · every figure, every citation`}
        </div>

        <div
          style={{
            fontFamily: SYS.body,
            fontSize: TYPE.body,
            color: SYS.text,
            marginTop: 34,
            maxWidth: 620,
            lineHeight: 1.4,
          }}
        >
          Body — the running line. Captions, epigraphs and subtitles sit here, never in Display.
        </div>
        <div style={{ fontFamily: SYS.data, fontSize: TYPE.dataSm - 4, color: SYS.faint, marginTop: 6 }}>
          {`sans 400 · ${TYPE.body}/${TYPE.bodySm} px`}
        </div>
      </div>

      {/* right: palette, motion, grade */}
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontFamily: SYS.label,
            fontSize: TYPE.labelSm - 5,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            color: SYS.accent,
            marginBottom: 26,
          }}
        >
          One primary, one accent, neutrals
        </div>
        <div style={{ display: "flex", gap: 30, flexWrap: "wrap", marginBottom: 38 }}>
          <Swatch name="plate" hex={SYS.bg} />
          <Swatch name="text" hex={SYS.text} />
          <Swatch name="accent" hex={SYS.accent} />
          <Swatch name="rule" hex={SYS.rule} />
          <Swatch name="paper" hex={SYS.paper} />
        </div>

        <div
          style={{
            fontFamily: SYS.label,
            fontSize: TYPE.labelSm - 5,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            color: SYS.accent,
            marginBottom: 12,
          }}
        >
          Motion language — locked
        </div>
        <Row k="tone" v="calm + sharp" />
        <Row k="entrance easing" v={`cubic-bezier(${EXPO_OUT.join(", ")})`} />
        <Row k="move easing" v={`cubic-bezier(${EXPO_IN_OUT.join(", ")})`} />
        <Row k="base unit" v={`${SYS.unit}f @30 = 0.40s · micro ${SYS.micro}f · move ${SYS.move}f`} />
        <Row k="stagger" v={`${SYS.stagger}f per element`} />
        <Row k="entrance" v={`blur ${SYS.blurFrom}px → 0, rise ${SYS.rise}px, no overshoot`} />
        <Row k="hold" v={`≥ ${SYS.hold}f of stillness after each beat`} />
        <Row k="transitions" v="cut · dissolve 12–20f · fade to black · grain leak" />
        <Row k="grade" v={`sat ${GRADE.saturation} · con ${GRADE.contrast} · lifted blacks`} />
      </div>
    </div>
  </SceneShell>
);
