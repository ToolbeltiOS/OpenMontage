import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, EXPO_IN_OUT } from "../design/system";
import { SceneShell } from "../design/Scene";
import { Graded } from "../design/Frame";

export interface StillAnnotation {
  /** Short label, e.g. "corbelled course" */
  label: string;
  /** Anchor point in 0..1 of the frame */
  x: number;
  y: number;
  /** Draw a leader line from the label box to the anchor */
  leader?: boolean;
  /** Seconds into the scene when this annotation appears */
  reveal_at: number;
  /** Which side the label sits on. Default auto from x. */
  side?: "left" | "right";
}

export interface MeasurementCallout {
  text: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  reveal_at: number;
}

export interface CutawayMask {
  x: number;
  y: number;
  w: number;
  h: number;
  reveal_at: number;
  label?: string;
}

export interface AnnotatedStillProps {
  image: string;
  /** Slow push-in. The playbook requires a move on every still. */
  parallax?: boolean;
  parallaxFrom?: number;
  parallaxTo?: number;
  annotations?: StillAnnotation[];
  measurement?: MeasurementCallout;
  cutaway?: CutawayMask;
  caption?: string;
  source?: string;
  title?: string;
  kicker?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
  dim?: number;
}

/**
 * The default vehicle for cross-section / diagram slots: a real sourced still
 * with ordered annotations drawn over it. Keeps the film photographic instead
 * of turning every explanatory beat into a text card.
 *
 * Annotation hierarchy, per the motion spec: the anchor ring is Hero (it draws
 * on), the label is Support (blur-to-sharp, 8px rise, staggered), the parallax
 * is Texture (1.0 -> 1.08 across the whole scene, below perception).
 */
export const AnnotatedStill: React.FC<AnnotatedStillProps> = ({
  image,
  parallax = true,
  parallaxFrom = 1.0,
  parallaxTo = 1.08,
  annotations = [],
  measurement,
  cutaway,
  caption,
  source,
  title,
  kicker,
  actNumber,
  actTitle,
  sceneIndex,
  coords,
  dim = 0.22,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();

  const scale = parallax
    ? interpolate(frame, [0, durationInFrames], [parallaxFrom, parallaxTo], {
        extrapolateRight: "clamp",
        easing: Easing.bezier(...EXPO_IN_OUT),
      })
    : 1;

  const appear = (atSeconds: number, frames: number = SYS.unit) =>
    interpolate(frame, [atSeconds * fps, atSeconds * fps + frames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    });

  return (
    <SceneShell
      caption={caption}
      source={source}
      title={title}
      kicker={kicker}
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      coords={coords}
    >
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        <Graded>
          <Img src={image} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </Graded>
      </AbsoluteFill>

      {/* hold the plate down so annotations stay legible */}
      <AbsoluteFill style={{ backgroundColor: `rgba(12,12,14,${dim})` }} />

      {cutaway ? (
        <AbsoluteFill style={{ opacity: appear(cutaway.reveal_at) }}>
          <svg width={width} height={height} style={{ position: "absolute" }}>
            <defs>
              <mask id="cutaway-mask">
                <rect x={0} y={0} width={width} height={height} fill="white" />
                <rect
                  x={cutaway.x * width}
                  y={cutaway.y * height}
                  width={cutaway.w * width}
                  height={cutaway.h * height}
                  fill="black"
                />
              </mask>
            </defs>
            <rect
              x={0}
              y={0}
              width={width}
              height={height}
              fill="rgba(12,12,14,0.62)"
              mask="url(#cutaway-mask)"
            />
            <rect
              x={cutaway.x * width}
              y={cutaway.y * height}
              width={cutaway.w * width}
              height={cutaway.h * height}
              fill="none"
              stroke={SYS.accent}
              strokeWidth={1.5}
            />
          </svg>
          {cutaway.label ? (
            <div
              style={{
                position: "absolute",
                left: cutaway.x * width,
                top: cutaway.y * height - 34,
                color: SYS.accent,
                fontFamily: SYS.label,
                fontWeight: 500,
                fontSize: TYPE.labelSm - 3,
                letterSpacing: TRACK,
                textTransform: "uppercase",
              }}
            >
              {cutaway.label}
            </div>
          ) : null}
        </AbsoluteFill>
      ) : null}

      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        {annotations.map((a, i) => {
          const o = appear(a.reveal_at);
          if (o <= 0) return null;
          const ax = a.x * width;
          const ay = a.y * height;
          const side = a.side ?? (a.x > 0.55 ? "left" : "right");
          const dx = side === "right" ? 92 : -92;
          return (
            <g key={i}>
              {/* ring draws on; dot is the fixed anchor */}
              <circle cx={ax} cy={ay} r={7} fill={SYS.accent} opacity={o} />
              <circle
                cx={ax}
                cy={ay}
                r={18}
                fill="none"
                stroke={SYS.accent}
                strokeWidth={1.5}
                opacity={0.55}
                pathLength={1}
                strokeDasharray={1}
                strokeDashoffset={1 - o}
              />
              {a.leader !== false ? (
                <line
                  x1={ax}
                  y1={ay}
                  x2={ax + dx * o}
                  y2={ay - 46 * o}
                  stroke={SYS.accent}
                  strokeWidth={1}
                  opacity={0.9}
                />
              ) : null}
            </g>
          );
        })}

        {measurement
          ? (() => {
              const o = appear(measurement.reveal_at, SYS.move);
              if (o <= 0) return null;
              const x1 = measurement.from.x * width;
              const y1 = measurement.from.y * height;
              const x2 = measurement.to.x * width;
              const y2 = measurement.to.y * height;
              const mx = (x1 + x2) / 2;
              const my = (y1 + y2) / 2;
              return (
                <g>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x1 + (x2 - x1) * o}
                    y2={y1 + (y2 - y1) * o}
                    stroke={SYS.text}
                    strokeWidth={1.5}
                  />
                  <line x1={x1} y1={y1 - 10} x2={x1} y2={y1 + 10} stroke={SYS.text} strokeWidth={1.5} opacity={o} />
                  <line x1={x2} y1={y2 - 10} x2={x2} y2={y2 + 10} stroke={SYS.text} strokeWidth={1.5} opacity={o} />
                  <text
                    x={mx}
                    y={my - 22}
                    fill={SYS.text}
                    fontFamily={SYS.data}
                    fontSize={TYPE.dataSm}
                    textAnchor="middle"
                    opacity={o}
                    style={{ paintOrder: "stroke", stroke: "rgba(12,12,14,0.85)", strokeWidth: 6 }}
                  >
                    {measurement.text}
                  </text>
                </g>
              );
            })()
          : null}
      </svg>

      {annotations.map((a, i) => {
        const o = appear(a.reveal_at);
        if (o <= 0) return null;
        const side = a.side ?? (a.x > 0.55 ? "left" : "right");
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: side === "right" ? a.x * width + 92 : undefined,
              right: side === "left" ? (1 - a.x) * width + 92 : undefined,
              top: a.y * height - 46 - 22,
              opacity: o,
              filter: o < 1 ? `blur(${(1 - o) * SYS.blurFrom}px)` : undefined,
              transform: `translateY(${(1 - o) * SYS.rise}px)`,
              background: "rgba(12,12,14,0.78)",
              borderLeft: `2px solid ${SYS.accent}`,
              padding: "9px 16px",
              color: SYS.text,
              fontFamily: SYS.label,
              fontWeight: 500,
              fontSize: TYPE.labelSm,
              letterSpacing: TRACK,
              textTransform: "uppercase",
              whiteSpace: "nowrap",
            }}
          >
            {a.label}
          </div>
        );
      })}
    </SceneShell>
  );
};
