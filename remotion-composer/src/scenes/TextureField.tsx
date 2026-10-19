import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, random, Easing } from "remotion";
import { SYS, EXPO_IN_OUT, GRADE } from "../design/system";
import { FrameLayer, Plate } from "../design/Frame";

export type TextureKind = "dust" | "strata" | "grain_drift" | "depth_field" | "scanline";

export interface TextureFieldProps {
  /** which family of movement; each reads differently on screen */
  kind: TextureKind;
  /** every instance must differ — the seed is what makes two configs distinct */
  seed: string;
  /** element count; density, not speed, carries the weight of a texture beat */
  density?: number;
  /** degrees; the drift direction */
  angle?: number;
  /** 0..1, multiplies the base drift */
  speed?: number;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  caption?: string;
}

/**
 * Authored texture, for when the clip bank runs out.
 *
 * The reuse rule allows a texture clip once. With 41 texture beats and 28
 * screened clips, thirteen have to come from somewhere, and repeating a clip
 * is the defect being fixed. This is a template: the same component with a
 * different seed, kind, density and angle is a different configuration, which
 * the rule permits — identical configurations are what it forbids.
 *
 * Deliberately subliminal. A texture beat sits under narration and should
 * read as the film breathing, not as a graphic demanding attention.
 */
export const TextureField: React.FC<TextureFieldProps> = ({
  kind,
  seed,
  density = 60,
  angle = 12,
  speed = 1,
  actNumber,
  actTitle,
  sceneIndex,
  caption,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const rad = (angle * Math.PI) / 180;

  const drift = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  const items = Array.from({ length: Math.round(density) }, (_, i) => {
    const r1 = random(`${seed}-x-${i}`);
    const r2 = random(`${seed}-y-${i}`);
    const r3 = random(`${seed}-s-${i}`);
    const r4 = random(`${seed}-o-${i}`);
    const travel = (0.05 + r3 * 0.25) * speed;
    const x = ((r1 + Math.cos(rad) * drift * travel) % 1) * width;
    const y = ((r2 + Math.sin(rad) * drift * travel) % 1) * height;
    return { x, y, r3, r4, i };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg, overflow: "hidden" }}>
      <Plate />
      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        {kind === "strata"
          ? items.map(({ y, r3, r4, i }) => (
              <line
                key={i}
                x1={0}
                y1={y}
                x2={width}
                y2={y + (r3 - 0.5) * 60}
                stroke={SYS.rule}
                strokeWidth={0.5 + r3 * 1.4}
                opacity={0.05 + r4 * 0.16}
              />
            ))
          : kind === "scanline"
          ? items.map(({ y, r4, i }) => (
              <rect key={i} x={0} y={y} width={width} height={1} fill={SYS.text} opacity={0.03 + r4 * 0.06} />
            ))
          : items.map(({ x, y, r3, r4, i }) => (
              <circle
                key={i}
                cx={x}
                cy={y}
                r={kind === "depth_field" ? 2 + r3 * 26 : 0.8 + r3 * 3.2}
                fill={kind === "grain_drift" ? SYS.muted : SYS.accentDim}
                opacity={
                  kind === "depth_field" ? 0.03 + r4 * 0.07 : 0.06 + r4 * 0.18
                }
              />
            ))}
      </svg>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at center, transparent 36%, rgba(0,0,0,${GRADE.vignette}) 100%)`,
        }}
      />
      <FrameLayer
        actNumber={actNumber}
        actTitle={actTitle}
        sceneIndex={sceneIndex}
        hairline={false}
      />
    </AbsoluteFill>
  );
};
