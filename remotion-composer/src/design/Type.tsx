import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, stagger } from "./system";
import { TYPE_CLASS } from "./layers";

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
 *
 * The rise lands on WHOLE PIXELS. An 8px rise eased over nine frames puts a
 * glyph on a fractional baseline for most of them, and a glyph on a
 * fractional baseline is re-rasterised every frame: the stems get redrawn
 * across different subpixels and the line crawls. Rounded, the text steps up
 * eight times and is still for the rest, and the entrance is carried by the
 * blur and the opacity, which cost nothing in sharpness because they do not
 * move anything.
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

  const rise = Math.round((1 - p) * SYS.rise);

  return (
    <div
      className={TYPE_CLASS}
      style={{
        opacity: p,
        filter: p < 1 ? `blur(${(1 - p) * SYS.blurFrom}px)` : undefined,
        // translateZ(0) gives the glyphs their own composited layer, so they
        // are rasterised once at an integer offset instead of being resampled
        // against whatever is behind them.
        transform: noRise || rise === 0
          ? "translateZ(0)"
          : `translateZ(0) translateY(${rise}px)`,
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
      className={TYPE_CLASS}
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
