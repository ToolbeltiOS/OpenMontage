import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT } from "../design/system";
import { SceneShell } from "../design/Scene";
import { TYPE_CLASS } from "../design/layers";

export type SchematicEffect = "draw" | "fade" | "slide-in";

export interface SchematicLayer {
  id: string;
  kind: "path" | "rect" | "circle" | "line" | "text" | "polyline";
  d?: string;
  x?: number;
  y?: number;
  x2?: number;
  y2?: number;
  w?: number;
  h?: number;
  r?: number;
  points?: string;
  text?: string;
  stroke?: string;
  fill?: string;
  strokeWidth?: number;
  fontSize?: number;
  dashed?: boolean;
  anchor?: "start" | "middle" | "end";
}

export interface SchematicReveal {
  layer_id: string;
  at: number;
  effect: SchematicEffect;
  duration?: number;
}

export interface SchematicLabel {
  text: string;
  x: number;
  y: number;
  at: number;
  anchor?: "start" | "middle" | "end";
  accent?: boolean;
  /** "data" for anything carrying a figure or a unit */
  level?: "label" | "data";
}

export interface SchematicProps {
  viewBox?: string;
  layers: SchematicLayer[];
  reveals?: SchematicReveal[];
  labels?: SchematicLabel[];
  title?: string;
  kicker?: string;
  caption?: string;
  source?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
}

/**
 * Authored vector schematic with a timed reveal sequence. Reserved for the
 * genuinely schematic scenes (sections, mechanisms) where a photograph cannot
 * show the thing — a pyramid in section, a tube drill cutting, a joint fitting.
 *
 * Draw-on is the only overshoot-free "motion" the system allows a line: the
 * stroke is dashed to its own length and the offset is eased out, so the line
 * is literally drawn rather than faded in.
 */
export const Schematic: React.FC<SchematicProps> = ({
  viewBox = "0 0 1920 1080",
  layers,
  reveals = [],
  labels = [],
  title,
  kicker,
  caption,
  source,
  actNumber,
  actTitle,
  sceneIndex,
  coords,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const revealOf = (id: string) => reveals.find((r) => r.layer_id === id);

  const progress = (at: number, dur: number) => {
    const s = at * fps;
    return interpolate(frame, [s, s + dur * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    });
  };

  return (
    <SceneShell
      title={title}
      kicker={kicker}
      caption={caption}
      source={source}
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      coords={coords}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        style={{ position: "absolute", inset: 0 }}
      >
        {layers.map((l) => {
          const rv = revealOf(l.id);
          const dur = rv?.duration ?? SYS.move / fps;
          const p = rv ? progress(rv.at, dur) : 1;
          if (p <= 0) return null;

          const stroke = l.stroke ?? SYS.text;
          const fill = l.fill ?? "none";
          const sw = l.strokeWidth ?? 2.5;
          const dash = l.dashed ? "10 8" : undefined;

          const effect = rv?.effect ?? "fade";
          let style: React.CSSProperties = { opacity: effect === "draw" ? 1 : p };
          if (effect === "slide-in") {
            style = { ...style, transform: `translateX(${(1 - p) * -60}px)` };
          }

          // "draw" animates stroke-dashoffset so the line is literally drawn on
          const drawProps =
            effect === "draw"
              ? { pathLength: 1 as const, strokeDasharray: 1, strokeDashoffset: 1 - p }
              : {};

          const common = {
            stroke,
            fill,
            strokeWidth: sw,
            strokeDasharray: dash,
            style,
            ...drawProps,
          } as any;

          switch (l.kind) {
            case "path":
              return <path key={l.id} d={l.d} {...common} />;
            case "rect":
              return <rect key={l.id} x={l.x} y={l.y} width={l.w} height={l.h} {...common} />;
            case "circle":
              return <circle key={l.id} cx={l.x} cy={l.y} r={l.r} {...common} />;
            case "line":
              return <line key={l.id} x1={l.x} y1={l.y} x2={l.x2} y2={l.y2} {...common} />;
            case "polyline":
              return <polyline key={l.id} points={l.points} {...common} />;
            case "text":
              return (
                <text className={TYPE_CLASS}
                  key={l.id}
                  x={l.x}
                  y={l.y}
                  fill={l.fill ?? SYS.text}
                  stroke="none"
                  fontFamily={SYS.label}
                  fontSize={l.fontSize ?? TYPE.labelSm}
                  textAnchor={l.anchor ?? "start"}
                  style={style}
                >
                  {l.text}
                </text>
              );
            default:
              return null;
          }
        })}

        {labels.map((lb, i) => {
          const p = progress(lb.at, SYS.unit / fps);
          if (p <= 0) return null;
          const isData = lb.level === "data";
          return (
            <text className={TYPE_CLASS}
              key={i}
              x={lb.x}
              y={lb.y + Math.round((1 - p) * SYS.rise)}
              fill={lb.accent ? SYS.accent : SYS.text}
              fontFamily={isData ? SYS.data : SYS.label}
              fontSize={isData ? TYPE.dataSm : TYPE.labelSm}
              fontWeight={isData ? 400 : 500}
              letterSpacing={TRACK}
              textAnchor={lb.anchor ?? "start"}
              opacity={p}
              style={{
                textTransform: isData ? "none" : "uppercase",
                // keep labels readable where they cross a drawn line
                paintOrder: "stroke",
                stroke: "rgba(12,12,14,0.8)",
                strokeWidth: 5,
              }}
            >
              {lb.text}
            </text>
          );
        })}
      </svg>
    </SceneShell>
  );
};
