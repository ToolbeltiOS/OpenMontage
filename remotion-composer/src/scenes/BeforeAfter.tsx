import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SYS, TYPE, TRACK, EXPO_IN_OUT, LAYOUT, SHADOW } from "../design/system";
import { Graded } from "../design/Frame";
import { SceneShell } from "../design/Scene";
import { T } from "../design/Type";

export interface BeforeAfterProps {
  /** the earlier framing — the state the scene starts in */
  before: string;
  /** the later framing of the SAME subject */
  after: string;
  before_label?: string;
  after_label?: string;
  /** "wipe" travels the divider across; "split" holds it and shows both */
  mode?: "wipe" | "split";
  /** seconds into the scene when the divider starts moving (wipe only) */
  at?: number;
  /** seconds the wipe takes */
  wipe_seconds?: number;
  /** where the divider rests, 0..1 from the left (split, and the wipe's end) */
  rest?: number;
  title?: string;
  caption?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
  kicker?: string;
  source?: string;
}

/**
 * One subject, two framings, divided.
 *
 * The whole point is that it is one subject: the two plates must be the same
 * place from the same angle, or the divider reads as a cut between two
 * pictures rather than as a comparison. Restoration and then-now beats are
 * what it is for.
 *
 * Both plates run through the same grade, so the difference the viewer sees is
 * the difference in the material and not a difference in treatment.
 */
export const BeforeAfter: React.FC<BeforeAfterProps> = ({
  before,
  after,
  before_label,
  after_label,
  mode = "wipe",
  at = 0.8,
  wipe_seconds = 2.2,
  rest = 0.62,
  title,
  caption,
  actNumber,
  actTitle,
  sceneIndex,
  coords,
  kicker,
  source,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;

  // The divider. In wipe mode it travels from just inside the left edge to
  // `rest`; in split mode it sits at `rest` and drifts by 1%, because the
  // playbook has no dead holds.
  const drift = Math.sin((frame / durationInFrames) * Math.PI) * 0.01;
  const p =
    mode === "wipe"
      ? interpolate(t, [at, at + wipe_seconds], [0.04, rest], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(...EXPO_IN_OUT),
        })
      : rest + drift;

  // A slow shared push, so neither plate is a static hold.
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.045], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  /**
   * Img, not a CSS background-image. Remotion blocks the frame until an Img
   * has decoded; a background-image is invisible to it, and the first render
   * of this scene caught the second plate undecoded and screenshotted half a
   * black frame.
   */
  const Plate: React.FC<{ src: string }> = ({ src }) => (
    <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  );

  // The labels hug the divider at mid-height. Along the bottom they collided
  // with the source caption, and the top belongs to the title and act strip.
  const labelStyle: React.CSSProperties = {
    position: "absolute",
    top: "50%",
    transform: "translateY(-50%)",
    fontFamily: SYS.label,
    fontSize: TYPE.labelSm,
    letterSpacing: TRACK,
    color: SYS.text,
    textShadow: SHADOW,
    opacity: 0.82,
    whiteSpace: "nowrap",
  };

  return (
    <SceneShell
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      coords={coords}
      kicker={kicker}
      source={source}
      title={title}
      caption={caption}
    >
      <AbsoluteFill style={{ backgroundColor: SYS.bg, overflow: "hidden" }}>
        <AbsoluteFill style={{ transform: `scale(${scale})` }}>
          <Graded strength={1}>
            <Plate src={before} />
          </Graded>
          {/* the later plate, clipped to the left of the divider */}
          <AbsoluteFill style={{ clipPath: `inset(0 ${(1 - p) * 100}% 0 0)` }}>
            <Graded strength={1}>
              <Plate src={after} />
            </Graded>
          </AbsoluteFill>
        </AbsoluteFill>

        {/* the divider: one ochre hairline, with a dark companion so it holds
            over a bright plate exactly as the frame's hairline does */}
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: `${p * 100}%`,
            width: 2,
            background: SYS.accent,
            boxShadow: SHADOW,
          }}
        />

        {after_label ? (
          <div
            style={{
              ...labelStyle,
              right: `calc(${(1 - p) * 100}% + 26px)`,
              textAlign: "right",
            }}
          >
            {after_label.toUpperCase()}
          </div>
        ) : null}
        {before_label ? (
          <div style={{ ...labelStyle, left: `calc(${p * 100}% + 26px)` }}>
            {before_label.toUpperCase()}
          </div>
        ) : null}
      </AbsoluteFill>
    </SceneShell>
  );
};

export default BeforeAfter;
