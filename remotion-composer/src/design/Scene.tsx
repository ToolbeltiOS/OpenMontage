import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, LAYOUT, SHADOW, stagger } from "./system";
import { FrameLayer, FrameLayerProps, Plate, PlateSweep } from "./Frame";
import { T } from "./Type";

/**
 * The scene title block. Top-left, under the data strip: a caps Label kicker,
 * a Display line, and a rule that draws out beneath it. Identical geometry in
 * every scene type, so the furniture never moves across a cut.
 */
export const SceneTitle: React.FC<{
  title?: string;
  kicker?: string;
  at?: number;
  ink?: { text: string; rule: string; accent: string };
}> = ({ title, kicker, at = 0.1, ink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!title && !kicker) return null;

  const ruleStart = at * fps + stagger(2);
  const ruleP = interpolate(frame, [ruleStart, ruleStart + SYS.move], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  return (
    <div style={{ position: "absolute", left: LAYOUT.left, top: LAYOUT.top + 40 }}>
      {kicker ? (
        <T
          level="label"
          size={TYPE.labelSm}
          color={ink?.accent ?? SYS.accent}
          at={at}
          index={0}
          style={{ textShadow: ink ? undefined : SHADOW }}
        >
          {kicker}
        </T>
      ) : null}
      {title ? (
        <T
          level="display"
          size={TYPE.displaySm}
          color={ink?.text}
          at={at}
          index={1}
          style={{ marginTop: kicker ? 12 : 0, textShadow: ink ? undefined : SHADOW }}
        >
          {title}
        </T>
      ) : null}
      {title ? (
        <div
          style={{
            marginTop: 18,
            width: LAYOUT.ruleWidth * ruleP,
            height: 1,
            background: ink?.rule ?? SYS.rule,
          }}
        />
      ) : null}
    </div>
  );
};

/**
 * Restyled source caption. Was a loose grey line; now a two-level block bound
 * to an accent tick — the claim's provenance, printed in the margin. The
 * attribution sits in the Data level so licences and author names read as
 * record, not as prose.
 */
export const SourceCaption: React.FC<{
  caption?: string;
  source?: string;
  at?: number;
  ink?: { text: string; faint: string; accent: string };
}> = ({ caption, source, at = 0.6, ink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!caption && !source) return null;

  const start = at * fps;
  const p = interpolate(frame, [start, start + SYS.unit], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.left,
        bottom: LAYOUT.bottom,
        display: "flex",
        gap: 16,
        alignItems: "stretch",
        maxWidth: 1100,
      }}
    >
      <div
        style={{
          width: 2,
          background: ink?.accent ?? SYS.accent,
          opacity: 0.85,
          transform: `scaleY(${p})`,
          transformOrigin: "bottom",
        }}
      />
      <div>
        {caption ? (
          <T
            level="body"
            size={TYPE.bodySm}
            at={at}
            index={0}
            color={ink?.text ?? SYS.text}
            noRise
            style={{ textShadow: ink ? undefined : SHADOW }}
          >
            {caption}
          </T>
        ) : null}
        {source ? (
          <T
            level="data"
            size={TYPE.dataSm - 3}
            at={at}
            index={1}
            color={ink?.faint ?? SYS.muted}
            noRise
            style={{ marginTop: 6, letterSpacing: "0.08em", textShadow: ink ? undefined : SHADOW }}
          >
            {source}
          </T>
        ) : null}
      </div>
    </div>
  );
};

/**
 * How far an authored scene drifts across its own hold, as a fraction of the
 * frame. Small enough that a viewer cannot name it; large enough that the
 * picture is never the same two frames running.
 *
 * WHY THIS EXISTS. The playbook has always required a move on every still —
 * "a static hold at this share reads as a slideshow immediately" — and
 * authored graphics were exempt, because in run #1 they were held 6-8s and
 * their own reveals covered most of that. Under beat-aware holds they are
 * held 8-15.5s, the reveals finish early, and the rest is a frozen frame:
 * measured at 90-95% duplicate frames per authored cut, with one run of 341
 * identical frames — 11.4 seconds — inside a 15.5s reveal. The exemption was
 * the bug.
 */
const AUTHORED_DRIFT = 0.030;
const AUTHORED_SCALE = 1.045;

/**
 * ...AND WHAT CARRIES IT (2026-10-21)
 *
 * The move was on the scene's content layer, which is where its type lives.
 * Moving type by a fraction of a pixel per frame does not move it — it
 * re-rasterises it, redistributing the same stems across different subpixels
 * every frame, and every edge in the frame shimmers.
 *
 * The obvious repair, locking the type and letting the graphic drift under
 * it, is wrong here and the measurement says so: at this amplitude a feature
 * at the frame edge travels about 72px over a 15.5s hold, so a label would
 * part company with the thing it labels. In an authored scene the labels ARE
 * the diagram — an evidence card is type on a rule, a timeline is dates on an
 * axis — and nothing in them can move independently of anything else.
 *
 * So in an authored scene the whole card is locked and the PLATE behind it
 * carries the move. Nobody reads the plate, which is exactly why it can take
 * a move; and the scene above it holds still, which is what type needs.
 *
 * A photographic scene is the other way round: the image moves, because it is
 * a photograph and not a page, and its annotations lock with their leaders
 * re-anchoring. That lives in AnnotatedStill, not here.
 */

export interface SceneShellProps extends Partial<FrameLayerProps> {
  children?: React.ReactNode;
  /** blurred backdrop image for the third plane; omit for the gradient plate */
  plate?: string;
  /** flat background instead of the plate (for paper and map scenes) */
  background?: string;
  title?: string;
  kicker?: string;
  title_at?: number;
  caption?: string;
  source?: string;
  caption_at?: number;
  /** turn off all persistent chrome (used by the act title cards) */
  chrome?: boolean;
  /**
   * The slow sustaining move under the scene's own animation. On by default:
   * a scene that stops moving when its reveals finish is a frozen frame, and
   * nothing downstream can tell that apart from a dropped frame.
   */
  sustain?: boolean;
  /**
   * Light-plate chrome. The paper scenes invert: the hairline, the data strip
   * and the caption all take the paper's ink instead of the film's off-white.
   */
  paperInk?: boolean;
}

/**
 * Every authored scene is a SceneShell: plate → content → chrome. The chrome
 * is identical everywhere, which is what makes a hundred different scenes read
 * as one film.
 */
export const SceneShell: React.FC<SceneShellProps> = ({
  children,
  plate,
  background,
  title,
  kicker,
  title_at = 0.1,
  caption,
  source,
  caption_at = 0.6,
  chrome = true,
  paperInk = false,
  sustain = true,
  ...frameProps
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // Linear, not eased: an eased drift spends its last seconds almost
  // stationary, which is the state being fixed.
  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 0;
  const plateStyle: React.CSSProperties = sustain
    ? {
        transform: `translateZ(0) scale(${1 + (AUTHORED_SCALE - 1) * progress}) `
          + `translateX(${AUTHORED_DRIFT * (progress - 0.5) * 100}%)`,
        // translateZ(0) and will-change force this onto its own composited
        // layer. Without them a slow transform is rasterised with pixel
        // snapping: the plate sits still for several frames and then jumps,
        // which is the stutter rather than a cure for it.
        willChange: "transform",
      }
    : {};
  // Everything above the plate is nailed down, on whole pixels, on its own
  // composited layer so it is rasterised once rather than resampled against
  // whatever is moving underneath it.
  const lockedStyle: React.CSSProperties = { transform: "translateZ(0)" };
  const ink = paperInk
    ? {
        rule: "rgba(36,31,24,0.30)",
        strip: "rgba(36,31,24,0.62)",
        faint: "rgba(36,31,24,0.48)",
        text: SYS.paperInk,
        accent: "#8A5A1E",
      }
    : undefined;
  return (
  <AbsoluteFill style={{ backgroundColor: background ?? SYS.bg, overflow: "hidden" }}>
    {/* The plate drifts. Everything above it — the scene, the chrome, every
        word in the frame — is locked. A flat-background scene has no plate to
        drift, so it takes the light sweep on its own: without it the frame
        would be motionless the moment its reveals finished, which is the
        defect the sustaining move exists to prevent. */}
    <AbsoluteFill style={plateStyle}>
      {background
        ? (sustain ? <PlateSweep /> : null)
        : <Plate image={plate} sweep={sustain} />}
    </AbsoluteFill>
    <AbsoluteFill style={lockedStyle}>{children}</AbsoluteFill>
    {chrome ? (
      <AbsoluteFill style={lockedStyle}>
        <FrameLayer {...frameProps} ink={ink} vignette={!paperInk && frameProps.vignette !== false} />
        <SceneTitle title={title} kicker={kicker} at={title_at} ink={ink} />
        <SourceCaption caption={caption} source={source} at={caption_at} ink={ink} />
      </AbsoluteFill>
    ) : null}
  </AbsoluteFill>
  );
};

/** Shared appear ramp. Entrance timing is the system's, not the component's. */
export const useAppear = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (atSeconds: number, frames: number = SYS.unit, index = 0) =>
    interpolate(
      frame,
      [atSeconds * fps + stagger(index), atSeconds * fps + stagger(index) + frames],
      [0, 1],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.bezier(...EXPO_OUT),
      },
    );
};

export { TRACK };
