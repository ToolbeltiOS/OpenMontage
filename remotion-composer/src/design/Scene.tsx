import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, LAYOUT, SHADOW, stagger } from "./system";
import { FrameLayer, FrameLayerProps, Plate } from "./Frame";
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
  ...frameProps
}) => {
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
    {background ? null : <Plate image={plate} />}
    {children}
    {chrome ? (
      <>
        <FrameLayer {...frameProps} ink={ink} vignette={!paperInk && frameProps.vignette !== false} />
        <SceneTitle title={title} kicker={kicker} at={title_at} ink={ink} />
        <SourceCaption caption={caption} source={source} at={caption_at} ink={ink} />
      </>
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
