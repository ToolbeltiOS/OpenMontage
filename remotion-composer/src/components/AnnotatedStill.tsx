import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, EXPO_IN_OUT } from "../design/system";
import { SceneShell } from "../design/Scene";
import { resolveAsset } from "../lib/resolveAsset";
import { Graded } from "../design/Frame";
import { TYPE_CLASS } from "../design/layers";

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
  /**
   * Lateral drift across the frame, as a fraction of its width. A drift of
   * 0.04 moves the plate 4% of the width over the shot. The scale is raised
   * automatically to cover it, because a drift on a plate at scale 1 shows
   * the edge of the picture.
   */
  driftFrom?: number;
  driftTo?: number;
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
  driftFrom = 0,
  driftTo = 0,
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

  const rawScale = parallax
    ? interpolate(frame, [0, durationInFrames], [parallaxFrom, parallaxTo], {
        extrapolateRight: "clamp",
        easing: Easing.bezier(...EXPO_IN_OUT),
      })
    : 1;
  const drift = interpolate(frame, [0, durationInFrames], [driftFrom, driftTo], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });
  // A drift at scale 1 slides the edge of the picture into frame. The cover
  // is twice the largest excursion, because the plate moves both ways from
  // centre.
  const cover = 1 + 2 * Math.max(Math.abs(driftFrom), Math.abs(driftTo));
  const scale = Math.max(rawScale, cover);

  /**
   * Where a point of the PHOTOGRAPH is on screen, once the image has moved.
   *
   * The image layer carries `scale(S) translateX(D%)`, which CSS applies
   * right to left about the element's centre: a point travels by D first and
   * is then scaled away from the middle. D is a percentage of the element's
   * own width, so it is `drift * width` in pixels.
   *
   * This is the only place the camera move is inverted, and it has to agree
   * with the style below exactly — a sign or an ordering wrong here puts
   * every anchor somewhere plausible and wrong.
   */
  const toScreen = (nx: number, ny: number): [number, number] => [
    width / 2 + scale * (nx * width + drift * width - width / 2),
    height / 2 + scale * (ny * height - height / 2),
  ];

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
      <AbsoluteFill style={{ transform: `scale(${scale}) translateX(${drift * 100}%)` }}>
        <Graded act={actNumber}>
          <Img src={resolveAsset(image)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
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
            <div className={TYPE_CLASS}
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

      {/*
        AN ANNOTATION HAS ITS TWO ENDS IN DIFFERENT COORDINATE SYSTEMS.

        The anchor is a point on the PHOTOGRAPH — "the dolerite pounder is
        here" — so it travels with the photograph, through `toScreen` below.
        The label is type, so it is locked: type moved by a fraction of a
        pixel is re-rasterised rather than moved, and every edge crawls. The
        leader is what makes that possible. It is redrawn every frame between
        the moving anchor and the locked label, which is the whole reason an
        annotation can do this and a plain overlay cannot.

        That is the rule, and it is also the limit: AN OVERLAY WITH A LEADER
        CAN HAVE ITS ENDS IN TWO COORDINATE SYSTEMS; ONE WITHOUT A LEADER
        CANNOT. The measurement and the cutaway below have no leader — a
        dimension's number sits on its own line, a cutaway's label sits on its
        own box — so each stays locked as a unit. A number that has drifted
        away from its line is worse than a line that has drifted slightly off
        its feature, and a number that moves is the defect all of this began
        with.
      */}
      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        {annotations.map((a, i) => {
          const o = appear(a.reveal_at);
          if (o <= 0) return null;
          // the anchor rides the photograph; the label's end of the leader
          // is where the locked label is, and does not
          const [ax, ay] = toScreen(a.x, a.y);
          const side = a.side ?? (a.x > 0.55 ? "left" : "right");
          const lx = a.x * width + (side === "right" ? 92 : -92);
          const ly = a.y * height - 46;
          return (
            <g key={i}>
              {/* ring draws on; dot marks the feature, wherever it has got to */}
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
                  x2={ax + (lx - ax) * o}
                  y2={ay + (ly - ay) * o}
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
                  <text className={TYPE_CLASS}
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
          <div className={TYPE_CLASS}
            key={i}
            style={{
              position: "absolute",
              left: side === "right" ? a.x * width + 92 : undefined,
              right: side === "left" ? (1 - a.x) * width + 92 : undefined,
              top: a.y * height - 46 - 22,
              opacity: o,
              filter: o < 1 ? `blur(${(1 - o) * SYS.blurFrom}px)` : undefined,
              transform: `translateZ(0) translateY(${Math.round((1 - o) * SYS.rise)}px)`,
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
