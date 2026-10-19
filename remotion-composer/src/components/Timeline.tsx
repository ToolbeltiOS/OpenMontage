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
  /** px; events closer together than this count as one cluster */
  cluster_px?: number;
  /** frames the playhead rests at each cluster */
  cluster_hold?: number;
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
  cluster_px = 110,
  cluster_hold = 12,
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

  /**
   * The axis stays linear — the empty stretch between antiquity and the modern
   * results is the act's argument, not a layout problem. What has to give is
   * the labels: 1922 and 2017 land ~35px apart on a 3,400-year axis, so each
   * label is measured, assigned a side, and pushed into a deeper lane when it
   * would touch the previous label on that side. The leader tick grows with
   * the lane so every label still points at its own mark.
   */
  const laid = useMemo(() => {
    const CHAR = 0.66; // caps Inter at TYPE.labelSm, with tracking
    const measured = events
      .map((e, i) => {
        const labelW = e.label.length * TYPE.labelSm * CHAR;
        const yearW = String(Math.abs(e.year)).length * TYPE.dataSm * 0.62 + 46;
        return { e, i, p: pos(e.year), half: Math.max(labelW, yearW) / 2 };
      })
      .sort((a, b) => a.p - b.p);

    const lastRight: Record<number, number> = {}; // side*100 + lane -> right edge
    const out = measured.map((m, order) => {
      const up = order % 2 === 0;
      const sideKey = up ? 0 : 1;
      let lane = 0;
      while ((lastRight[sideKey * 100 + lane] ?? -Infinity) > m.p - m.half - 18) lane++;
      lastRight[sideKey * 100 + lane] = m.p + m.half;
      return { ...m, up, lane };
    });
    // back to authored order so reveal timings read in the plan's sequence
    return out.sort((a, b) => a.i - b.i);
  }, [events, lo, hi, horizontal, padL, usableW, usableH]);

  /**
   * Clusters: where marks crowd, the playhead rests rather than sliding past.
   * It is the only place in the film where a moving element stops mid-travel,
   * and it is doing the same job as a held shot.
   */
  const { stops, playAt } = useMemo(() => {
    const xs = [...laid].map((l) => l.p).sort((a, b) => a - b);
    const groups: number[][] = [];
    for (const x of xs) {
      const g = groups[groups.length - 1];
      if (g && x - g[g.length - 1] <= cluster_px) g.push(x);
      else groups.push([x]);
    }
    const centres = groups
      .filter((g) => g.length > 1)
      .map((g) => g.reduce((a, b) => a + b, 0) / g.length);

    const startPos = horizontal ? padL : 200;
    const endPos = horizontal ? padL + usableW : 200 + usableH;
    const pts = [startPos, ...centres.filter((c) => c > startPos && c < endPos), endPos];
    const totalDist = Math.max(1, endPos - startPos);
    const moveFrames = Math.max(1, durationInFrames - centres.length * cluster_hold);

    // [frameStart, frameEnd, posStart, posEnd] segments, holds included
    const segs: [number, number, number, number][] = [];
    let f = 0;
    for (let i = 0; i < pts.length - 1; i++) {
      const dur = (Math.abs(pts[i + 1] - pts[i]) / totalDist) * moveFrames;
      segs.push([f, f + dur, pts[i], pts[i + 1]]);
      f += dur;
      if (i < pts.length - 2) {
        segs.push([f, f + cluster_hold, pts[i + 1], pts[i + 1]]);
        f += cluster_hold;
      }
    }
    const at = (fr: number) => {
      for (const [f0, f1, p0, p1] of segs) {
        if (fr <= f1) return p0 + (p1 - p0) * (f1 === f0 ? 1 : (fr - f0) / (f1 - f0));
      }
      return endPos;
    };
    return { stops: centres, playAt: at };
  }, [laid, cluster_px, cluster_hold, durationInFrames, horizontal, padL, usableW, usableH]);

  const appear = (at: number, frames: number = SYS.unit) =>
    interpolate(frame, [at * fps, at * fps + frames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    });

  // the axis draws itself once, then the events land on it
  const axisP = appear(0.05, SYS.move * 2);

  const headPos = playAt(frame);
  // the playhead brightens while it rests, so the pause reads as attention
  const resting = stops.some((c) => Math.abs(c - headPos) < 1.5);

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
              opacity={resting ? 0.75 : 0.35}
            />
          ) : (
            <line
              x1={axisX - 54}
              y1={headPos}
              x2={axisX + 54}
              y2={headPos}
              stroke={SYS.accent}
              strokeWidth={1}
              opacity={resting ? 0.75 : 0.35}
            />
          )
        ) : null}

        {laid.map(({ e, i, p, up, lane }) => {
          const o = appear(e.at);
          if (o <= 0) return null;
          const col = e.accent ? SYS.accent : SYS.text;
          const lift = (1 - o) * SYS.rise;
          const LANE = 62;

          if (horizontal) {
            const dir = up ? -1 : 1;
            // the leader tick grows with the lane so a pushed label still
            // points at its own mark rather than at its neighbour's
            const tickEnd = axisY + dir * (26 + lane * LANE);
            const yearY = tickEnd + dir * 24;
            const labelY = yearY + dir * 30;
            return (
              <g key={i}>
                <line
                  x1={p}
                  y1={axisY}
                  x2={p}
                  y2={axisY + (tickEnd - axisY) * o}
                  stroke={col}
                  strokeWidth={1.5}
                />
                <circle cx={p} cy={axisY} r={5} fill={col} opacity={o} />
                <text
                  x={p}
                  y={yearY + lift}
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
                  y={labelY + lift}
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

          const tickEnd = axisX + 30 + lane * LANE;
          return (
            <g key={i}>
              <line
                x1={axisX}
                y1={p}
                x2={axisX + (tickEnd - axisX) * o}
                y2={p}
                stroke={col}
                strokeWidth={1.5}
              />
              <circle cx={axisX} cy={p} r={5} fill={col} opacity={o} />
              <text
                x={tickEnd + 16}
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
                x={tickEnd + 16}
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
