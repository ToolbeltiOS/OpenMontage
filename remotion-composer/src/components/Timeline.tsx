import React, { useMemo } from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, LAYOUT } from "../design/system";
import { SceneShell } from "../design/Scene";

export interface TimelineEvent {
  /** Negative = BC. 1922 = AD 1922, -1400 = 1400 BC. */
  year: number;
  label: string;
  text?: string;
  at: number;
  accent?: boolean;
}

export interface TimelineProps {
  events: TimelineEvent[];
  orientation?: "horizontal" | "vertical";
  /** [start, end] in the same signed-year convention; inferred when omitted */
  span?: [number, number];
  playhead?: boolean;
  title?: string;
  kicker?: string;
  caption?: string;
  source?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
}

const fmtYear = (y: number) => {
  // Years never take thousands separators: "AD 2017", not "AD 2,017".
  // BC values above 9999 are rare enough that plain digits stay readable.
  const n = Math.abs(y);
  return y < 0 ? `${n} BC` : `AD ${n}`;
};

/**
 * Timeline with BC/AD spans and a moving playhead. Carries the film's
 * chronology beats — construction 1400-1200 BC against Pausanias in the 2nd
 * century, the Younger Dryas, the 2017 and 2023 muon results.
 *
 * Years sit in the Data level (tabular, mono) and the event in the Label level,
 * so the eye separates "when" from "what" without a second colour.
 */
export const Timeline: React.FC<TimelineProps> = ({
  events,
  orientation = "horizontal",
  span,
  playhead = true,
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
  const { fps, width, height, durationInFrames } = useVideoConfig();

  const [lo, hi] = useMemo(() => {
    if (span) return span;
    const ys = events.map((e) => e.year);
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    const pad = Math.max(120, (max - min) * 0.12);
    return [min - pad, max + pad] as [number, number];
  }, [events, span]);

  const horizontal = orientation === "horizontal";
  const padL = LAYOUT.left + 110;
  const padR = LAYOUT.left + 110;
  const axisY = height * 0.58;
  const axisX = width * 0.3;
  const usableW = width - padL - padR;
  const usableH = height - 340;

  const pos = (y: number) => {
    const t = (y - lo) / (hi - lo || 1);
    return horizontal ? padL + t * usableW : 200 + t * usableH;
  };

  const appear = (at: number, frames: number = SYS.unit) =>
    interpolate(frame, [at * fps, at * fps + frames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    });

  // the axis draws itself once, then the events land on it
  const axisP = appear(0.05, SYS.move * 2);

  const headT = interpolate(frame, [0, durationInFrames], [0, 1], { extrapolateRight: "clamp" });
  const headPos = horizontal ? padL + headT * usableW : 200 + headT * usableH;

  const stroked = {
    paintOrder: "stroke" as const,
    stroke: "rgba(12,12,14,0.85)",
    strokeWidth: 6,
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
      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        {horizontal ? (
          <line
            x1={padL}
            y1={axisY}
            x2={padL + usableW * axisP}
            y2={axisY}
            stroke={SYS.rule}
            strokeWidth={1.5}
          />
        ) : (
          <line
            x1={axisX}
            y1={200}
            x2={axisX}
            y2={200 + usableH * axisP}
            stroke={SYS.rule}
            strokeWidth={1.5}
          />
        )}

        {playhead ? (
          horizontal ? (
            <line
              x1={headPos}
              y1={axisY - 54}
              x2={headPos}
              y2={axisY + 54}
              stroke={SYS.accent}
              strokeWidth={1}
              opacity={0.35}
            />
          ) : (
            <line
              x1={axisX - 54}
              y1={headPos}
              x2={axisX + 54}
              y2={headPos}
              stroke={SYS.accent}
              strokeWidth={1}
              opacity={0.35}
            />
          )
        ) : null}

        {events.map((e, i) => {
          const o = appear(e.at);
          if (o <= 0) return null;
          const p = pos(e.year);
          const up = i % 2 === 0;
          const col = e.accent ? SYS.accent : SYS.text;
          const lift = (1 - o) * SYS.rise;

          if (horizontal) {
            const tickTop = up ? axisY - 24 : axisY + 24;
            const labelY = up ? axisY - 50 : axisY + 74;
            return (
              <g key={i}>
                <line
                  x1={p}
                  y1={axisY}
                  x2={p}
                  y2={axisY + (tickTop - axisY) * o}
                  stroke={col}
                  strokeWidth={1.5}
                />
                <circle cx={p} cy={axisY} r={5} fill={col} opacity={o} />
                <text
                  x={p}
                  y={labelY + lift}
                  fill={col}
                  fontFamily={SYS.data}
                  fontSize={TYPE.dataSm}
                  textAnchor="middle"
                  opacity={o}
                  style={stroked}
                >
                  {fmtYear(e.year)}
                </text>
                <text
                  x={p}
                  y={labelY + (up ? -30 : 30) + lift}
                  fill={SYS.text}
                  fontFamily={SYS.label}
                  fontSize={TYPE.labelSm}
                  fontWeight={500}
                  letterSpacing={TRACK}
                  textAnchor="middle"
                  opacity={o * 0.92}
                  style={{ textTransform: "uppercase", ...stroked }}
                >
                  {e.label}
                </text>
              </g>
            );
          }
          return (
            <g key={i}>
              <line x1={axisX} y1={p} x2={axisX + 30 * o} y2={p} stroke={col} strokeWidth={1.5} />
              <circle cx={axisX} cy={p} r={5} fill={col} opacity={o} />
              <text
                x={axisX + 46}
                y={p - 6 + lift}
                fill={col}
                fontFamily={SYS.data}
                fontSize={TYPE.dataSm}
                opacity={o}
                style={stroked}
              >
                {fmtYear(e.year)}
              </text>
              <text
                x={axisX + 46}
                y={p + 26 + lift}
                fill={SYS.text}
                fontFamily={SYS.label}
                fontSize={TYPE.labelSm}
                fontWeight={500}
                letterSpacing={TRACK}
                opacity={o * 0.92}
                style={{ textTransform: "uppercase", ...stroked }}
              >
                {e.label}
              </text>
            </g>
          );
        })}
      </svg>
    </SceneShell>
  );
};
