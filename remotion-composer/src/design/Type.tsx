import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, stagger } from "./system";

export type TypeLevel = "display" | "label" | "data" | "body";

export interface AnimatedTextProps {
  children: React.ReactNode;
  level?: TypeLevel;
  /** seconds from scene start */
  at?: number;
  /** index within a staggered group */
  index?: number;
  size?: number;
  color?: string;
  caps?: boolean;
  align?: "left" | "center" | "right";
  style?: React.CSSProperties;
  /** disable the rise (for elements pinned to an anchor) */
  noRise?: boolean;
}

const FAMILY: Record<TypeLevel, string> = {
  display: SYS.display,
  label: SYS.label,
  data: SYS.data,
  body: SYS.body,
};

const DEFAULT_SIZE: Record<TypeLevel, number> = {
  display: TYPE.display,
  label: TYPE.label,
  data: TYPE.data,
  body: TYPE.body,
};

const WEIGHT: Record<TypeLevel, number> = {
  display: 600,
  label: 500,
  data: 400,
  body: 400,
};

/**
 * Every text element in the film enters the same way: 6-10 frame blur-to-sharp
 * plus an 8px rise, expo-out, staggered 3 frames per element. Nothing pops.
 */
export const T: React.FC<AnimatedTextProps> = ({
  children,
  level = "body",
  at = 0,
  index = 0,
  size,
  color,
  caps,
  align = "left",
  style,
  noRise,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = at * fps + stagger(index);
  const dur = 9; // frames — inside the 6-10 window

  const p = interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  const isCaps = caps ?? level === "label";

  return (
    <div
      style={{
        opacity: p,
        filter: p < 1 ? `blur(${(1 - p) * SYS.blurFrom}px)` : undefined,
        transform: noRise ? undefined : `translateY(${(1 - p) * SYS.rise}px)`,
        fontFamily: FAMILY[level],
        fontSize: size ?? DEFAULT_SIZE[level],
        fontWeight: WEIGHT[level],
        color: color ?? SYS.text,
        letterSpacing: isCaps ? TRACK : level === "display" ? "-0.01em" : "0.01em",
        textTransform: isCaps ? "uppercase" : undefined,
        textAlign: align,
        // numbers always align in Data
        fontVariantNumeric: level === "data" ? "tabular-nums" : undefined,
        lineHeight: level === "display" ? 1.12 : 1.4,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Count-up number in the Data level. Used by measurements and distances. */
export const CountUp: React.FC<{
  to: number;
  at?: number;
  durationFrames?: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  size?: number;
  color?: string;
}> = ({ to, at = 0, durationFrames = SYS.move, suffix = "", prefix = "", decimals = 0, size, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = at * fps;
  const p = interpolate(frame, [start, start + durationFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });
  const v = (to * p).toFixed(decimals);
  return (
    <span
      style={{
        fontFamily: SYS.data,
        fontVariantNumeric: "tabular-nums",
        fontSize: size ?? TYPE.data,
        color: color ?? SYS.text,
      }}
    >
      {prefix}
      {Number(v).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
      {suffix}
    </span>
  );
};
