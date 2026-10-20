import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, random, Easing } from "remotion";
import { SYS, TYPE, TRACK, GRADE, EXPO_OUT, LAYOUT, SHADOW, gradeForAct } from "./system";

export interface DataStripProps {
  /** top-left: act number + act title */
  actNumber?: string;
  actTitle?: string;
  /** bottom-right: scene index + subject, e.g. "03 / TIRYNS" */
  sceneIndex?: string;
  /**
   * top-right, on the same baseline as the act strip. Used where the bottom
   * of the frame has to stay clear — an end card leaves the bottom fifth for
   * YouTube End Screen elements, so its channel mark goes up here instead.
   */
  topRight?: string;
  /** bottom-right second line: coordinates or a date */
  coords?: string;
}

export interface FrameLayerProps extends DataStripProps {
  /** hairline frame + corner ticks */
  hairline?: boolean;
  grain?: boolean;
  vignette?: boolean;
  chromatic?: boolean;
  /**
   * Top and bottom scrim bands. The data strip is a fixed colour, so on a
   * sunlit granite plate it has nothing to sit against; these guarantee it a
   * ground without tinting the middle of the image.
   */
  bands?: boolean;
  /** one scan/sweep line crossing at reveal */
  sweepAt?: number | null;
  opacity?: number;
  /**
   * Chrome ink. Defaults to the dark-plate palette; pass the paper ink for a
   * light plate so the hairline and the data strip stay visible.
   */
  ink?: { rule: string; strip: string; faint: string; accent?: string };
}

/**
 * Deterministic film grain. Seeded so renders are reproducible.
 *
 * One CSS tile on a 320px repeat, stepped every second frame.
 *
 * Measured alternatives, both rejected: two gradient layers repainting every
 * frame (the original) cost about 7% of render time against this; a data-URI
 * SVG `feTurbulence` tile cost 9x — 0.46fps against 4.09fps — because Chrome
 * re-evaluates the filter whenever the background position moves. Do not
 * "improve" this without measuring a full act.
 */
const Grain: React.FC<{ opacity: number }> = ({ opacity }) => {
  const frame = useCurrentFrame();
  const step = Math.floor(frame / 2);
  const ox = Math.round(random(`gx${step}`) * 64);
  const oy = Math.round(random(`gy${step}`) * 64);
  return (
    <AbsoluteFill
      style={{
        opacity,
        pointerEvents: "none",
        mixBlendMode: "overlay",
        backgroundImage:
          "repeating-radial-gradient(circle at 17% 29%, rgba(255,255,255,0.55) 0 0.6px, transparent 0.6px 2.1px)",
        backgroundSize: "320px 320px",
        backgroundPosition: `${ox}px ${oy}px`,
      }}
    />
  );
};

/**
 * The persistent frame. Sits on every authored scene and over every still or
 * clip. Forensic dossier, not HUD: it should read as printed on the image.
 */
export const FrameLayer: React.FC<FrameLayerProps> = ({
  actNumber,
  actTitle,
  sceneIndex,
  topRight,
  coords,
  hairline = true,
  grain = true,
  vignette = true,
  chromatic = true,
  bands = true,
  sweepAt = null,
  opacity = 1,
  ink,
}) => {
  const C = {
    rule: ink?.rule ?? SYS.rule,
    strip: ink?.strip ?? SYS.muted,
    faint: ink?.faint ?? SYS.muted,
    accent: ink?.accent ?? SYS.accent,
  };
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const inP = interpolate(frame, [0, SYS.unit], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  const M = LAYOUT.frameInset;
  const TICK = 26;

  const sweepP =
    sweepAt === null
      ? null
      : interpolate(frame, [sweepAt * fps, sweepAt * fps + 26], [-0.25, 1.25], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(...EXPO_OUT),
        });

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      {vignette ? (
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse at center, transparent 42%, rgba(0,0,0,${GRADE.vignette}) 100%)`,
          }}
        />
      ) : null}

      {chromatic ? (
        <AbsoluteFill
          style={{
            boxShadow: `inset ${GRADE.chromatic}px 0 0 rgba(120,160,255,0.16), inset ${-GRADE.chromatic}px 0 0 rgba(255,150,110,0.14)`,
          }}
        />
      ) : null}

      {bands && !ink ? (
        <>
          <AbsoluteFill
            style={{
              background: "linear-gradient(180deg, rgba(10,10,12,0.62) 0%, rgba(10,10,12,0.22) 9%, transparent 16%)",
            }}
          />
          <AbsoluteFill
            style={{
              background: "linear-gradient(0deg, rgba(10,10,12,0.72) 0%, rgba(10,10,12,0.26) 10%, transparent 18%)",
            }}
          />
        </>
      ) : null}

      {grain ? <Grain opacity={GRADE.grainOpacity} /> : null}

      {sweepP !== null && sweepP > -0.2 && sweepP < 1.2 ? (
        <AbsoluteFill
          style={{
            background: `linear-gradient(97deg, transparent ${(sweepP - 0.08) * 100}%, rgba(237,230,216,0.10) ${sweepP * 100}%, transparent ${(sweepP + 0.08) * 100}%)`,
            mixBlendMode: "screen",
          }}
        />
      ) : null}

      {hairline ? (
        <svg width={width} height={height} style={{ position: "absolute", inset: 0, opacity: inP * 0.75 }}>
          {/* a dark companion one pixel out, so the hairline survives a bright plate */}
          <rect
            x={M - 1}
            y={M - 1}
            width={width - M * 2 + 2}
            height={height - M * 2 + 2}
            fill="none"
            stroke="rgba(0,0,0,0.55)"
            strokeWidth={2}
          />
          <rect
            x={M}
            y={M}
            width={width - M * 2}
            height={height - M * 2}
            fill="none"
            stroke={C.rule}
            strokeWidth={1}
          />
          {[
            [M, M, 1, 1],
            [width - M, M, -1, 1],
            [M, height - M, 1, -1],
            [width - M, height - M, -1, -1],
          ].map(([x, y, sx, sy], i) => (
            <g key={i} stroke={C.accent} strokeWidth={1.5} style={{ filter: "drop-shadow(0 0 3px rgba(0,0,0,0.9))" }}>
              <line x1={x} y1={y} x2={x + sx * TICK} y2={y} />
              <line x1={x} y1={y} x2={x} y2={y + sy * TICK} />
            </g>
          ))}
        </svg>
      ) : null}

      {/* top-left data strip */}
      {actNumber || actTitle ? (
        <div
          style={{
            position: "absolute",
            left: LAYOUT.left,
            top: LAYOUT.top,
            opacity: inP * 0.9,
            display: "flex",
            alignItems: "baseline",
            gap: 14,
          }}
        >
          {actNumber ? (
            <span
              style={{
                fontFamily: SYS.data,
                fontSize: TYPE.dataSm,
                color: C.accent,
                letterSpacing: TRACK,
                fontVariantNumeric: "tabular-nums",
                textShadow: SHADOW,
              }}
            >
              {actNumber}
            </span>
          ) : null}
          {actTitle ? (
            <span
              style={{
                fontFamily: SYS.data,
                fontSize: TYPE.dataSm,
                color: C.strip,
                letterSpacing: TRACK,
                textTransform: "uppercase",
                textShadow: SHADOW,
              }}
            >
              {actTitle}
            </span>
          ) : null}
        </div>
      ) : null}

      {topRight ? (
        <div
          style={{
            position: "absolute",
            right: LAYOUT.left,
            top: LAYOUT.top,
            opacity: inP * 0.9,
            fontFamily: SYS.data,
            fontSize: TYPE.dataSm,
            color: C.strip,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            textShadow: SHADOW,
          }}
        >
          {topRight}
        </div>
      ) : null}

      {/* bottom-right scene index + coordinates */}
      {sceneIndex || coords ? (
        <div
          style={{
            position: "absolute",
            right: LAYOUT.left,
            bottom: LAYOUT.bottom,
            textAlign: "right",
            opacity: inP * 0.85,
          }}
        >
          {sceneIndex ? (
            <div
              style={{
                fontFamily: SYS.data,
                fontSize: TYPE.dataSm,
                color: C.strip,
                letterSpacing: TRACK,
                textTransform: "uppercase",
                fontVariantNumeric: "tabular-nums",
                textShadow: SHADOW,
              }}
            >
              {sceneIndex}
            </div>
          ) : null}
          {coords ? (
            <div
              style={{
                fontFamily: SYS.data,
                fontSize: TYPE.dataSm - 3,
                color: C.faint,
                letterSpacing: "0.1em",
                marginTop: 4,
                fontVariantNumeric: "tabular-nums",
                textShadow: SHADOW,
              }}
            >
              {coords}
            </div>
          ) : null}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

/**
 * Unified grade for stills and footage. Lifted blacks toward #0C0C0E, slight
 * desaturation, warm highlights toward the ochre, cool shadows.
 */
/**
 * Unified grade for stills and footage. Lifted blacks toward the film's own
 * background, slight desaturation, warm highlights, cool shadows.
 *
 * Folded into one filter chain and a single blended overlay. The earlier
 * version stacked four full-frame layers with three different blend modes,
 * which forced a separate compositing pass per layer on all 183 cuts.
 *
 * The overlay blends with `screen`, not `soft-light`. soft-light looked
 * marginally richer and cost about four times the render time — a measured
 * 1.0fps against 3.8fps, with single frames exceeding the 180s timeout.
 */
export const Graded: React.FC<{
  children: React.ReactNode;
  strength?: number;
  /**
   * Act number or section id. The film keeps one grade; this shifts its
   * temperature, saturation and lift by the act's own offsets, so a Greek
   * ridge and an Egyptian quarry are not the same colour. Photographic
   * material only — authored graphics are never wrapped in Graded and so
   * keep the base palette.
   */
  act?: string | number;
}> = ({ children, strength = 1, act }) => {
  const g = gradeForAct(act);
  return (
  <AbsoluteFill>
    <AbsoluteFill
      style={{
        // TWO filter functions, never three. Adding brightness() to this chain
        // measured 0.60fps against 4.15 — headless Chrome rasterises in
        // software and a third function evidently takes a different path. The
        // darkening it was doing is done by the flat wash below instead, which
        // is one cheap paint and achieves the same thing.
        filter:
          `saturate(${1 - (1 - g.saturation) * strength}) ` +
          `contrast(${1 + (GRADE.contrast - 1) * strength})`,
      }}
    >
      {children}
    </AbsoluteFill>
    <AbsoluteFill
      style={{
        background:
          `linear-gradient(170deg, ${GRADE.warmHighlights} 0%, transparent 52%, rgba(74,96,134,0.10) 100%)`,
        opacity: strength,
        mixBlendMode: "screen",
      }}
    />
    {/*
      * The brightness pull. Without it a bright blue-sky JPEG stays bright and
      * sits several stops from the authored scenes it cuts against, which is
      * the one thing the grade exists to prevent.
      */}
    {/* the act's temperature: one wash, warm or cool, never both */}
    <AbsoluteFill
      style={{
        background: g.temperature >= 0 ? GRADE.warmHighlights : GRADE.coolShadows,
        opacity: Math.abs(g.temperature) * strength,
        mixBlendMode: "screen",
      }}
    />
    <AbsoluteFill style={{ background: "#07070A", opacity: 0.15 * strength }} />
    <AbsoluteFill style={{ background: GRADE.lift, opacity: g.lift * strength }} />
  </AbsoluteFill>
  );
};

/** Three-plane background: treated plate behind the subject. */
export const Plate: React.FC<{ image?: string; children?: React.ReactNode }> = ({ image, children }) => (
  <AbsoluteFill style={{ backgroundColor: SYS.bg }}>
    {image ? (
      <AbsoluteFill
        style={{
          backgroundImage: `url(${image})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          filter: "blur(26px) saturate(0.5) brightness(0.42)",
          transform: "scale(1.12)",
        }}
      />
    ) : (
      <AbsoluteFill
        style={{
          background:
            `radial-gradient(ellipse at 28% 22%, ${SYS.surface} 0%, transparent 58%),` +
            `radial-gradient(ellipse at 76% 78%, #15131A 0%, transparent 62%)`,
        }}
      />
    )}
    {children}
  </AbsoluteFill>
);
