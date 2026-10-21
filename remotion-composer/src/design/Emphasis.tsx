import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, EXPO_OUT, EXPO_IN_OUT, LAYOUT, SHADOW } from "./system";
import { TYPE_CLASS } from "./layers";

export interface EmphasisLineProps {
  text: string;
  /** seconds, relative to the overlay's own sequence */
  at?: number;
  hold?: number;
  /**
   * "display" for a line of narration held on screen; "data" for a bare
   * figure, which belongs in the Data level like every other number in the
   * film rather than being set as prose.
   */
  level?: "display" | "data";
}

/**
 * The playbook's typographic emphasis beat: one sentence from the narration,
 * held over the picture.
 *
 * It sits in Display, not in the caption's Body, because it is not a subtitle —
 * it is the line the film wants you to stop on. It enters on the system's
 * entrance (blur-to-sharp, 8px rise) and leaves on the move easing, and it is
 * placed on the same left margin as every other piece of furniture so it reads
 * as part of the frame rather than as a sticker on top of it.
 */
export const EmphasisLine: React.FC<EmphasisLineProps> = ({ text, at = 0.4, hold = 2.6, level = "display" }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const start = at * fps;
  const inP = interpolate(frame, [start, start + SYS.unit], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });
  const outStart = Math.min(start + (hold + 0.4) * fps, durationInFrames - SYS.unit);
  const outP = interpolate(frame, [outStart, outStart + SYS.unit], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });
  const o = Math.min(inP, outP);
  if (o <= 0) return null;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* a soft pool so the line holds over a bright plate */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(90deg, rgba(10,10,12,0.72) 0%, rgba(10,10,12,0.40) 42%, transparent 68%)",
          opacity: o,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: LAYOUT.left + 40,
          top: "50%",
          transform: `translateY(calc(-50% + ${Math.round((1 - o) * SYS.rise)}px))`,
          maxWidth: 1020,
          opacity: o,
          filter: o < 1 ? `blur(${(1 - o) * SYS.blurFrom}px)` : undefined,
        }}
      >
        <div
          style={{
            width: 46,
            height: 2,
            background: SYS.accent,
            marginBottom: 22,
            transform: `scaleX(${o})`,
            transformOrigin: "left",
          }}
        />
        <div
          className={TYPE_CLASS}
          style={
            level === "data"
              ? {
                  fontFamily: SYS.data,
                  fontWeight: 400,
                  fontSize: TYPE.data + 6,
                  lineHeight: 1.4,
                  color: SYS.text,
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: "0.02em",
                  textShadow: SHADOW,
                }
              : {
                  fontFamily: SYS.display,
                  fontWeight: 600,
                  fontSize: TYPE.display - 8,
                  lineHeight: 1.16,
                  color: SYS.text,
                  letterSpacing: "-0.01em",
                  textShadow: SHADOW,
                }
          }
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
