import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, LAYOUT, stagger } from "../design/system";
import { SceneShell } from "../design/Scene";
import { T, CountUp } from "../design/Type";

export interface ScaleItem {
  label: string;
  value: number;
  /** a qualifier under the label: "estimated", "as cut", "Petrie 1883" */
  note?: string;
  /** the subject the film is arguing about — drawn in the accent */
  hero?: boolean;
}

export interface ScaleComparisonProps {
  items: ScaleItem[];
  /** what the numbers are: "tonnes", "metres", "km" */
  unit: string;
  decimals?: number;
  title?: string;
  kicker?: string;
  /** one line of honesty under the chart: the spread, the disagreement */
  footnote?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  caption?: string;
  source?: string;
  /** seconds; first bar starts here, the rest follow on the stagger */
  at?: number;
}

/**
 * Comparative magnitude. The film's hardest job is making a number felt — 1,000
 * tonnes against 80 tonnes against a person — and a spoken figure does not do
 * it. Bars grow on the system's move duration, staggered 3 frames, and the
 * numbers count up in the Data level so the digits land with the bar.
 *
 * Deliberately not a chart: no axes, no gridlines, no legend. One quantity,
 * compared.
 */
export const ScaleComparison: React.FC<ScaleComparisonProps> = ({
  items,
  unit,
  decimals = 0,
  title,
  kicker,
  footnote,
  actNumber,
  actTitle,
  sceneIndex,
  caption,
  source,
  at = 0.5,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const max = Math.max(...items.map((i) => i.value)) || 1;

  const footStart = (at + 0.1) * fps + stagger(items.length) + SYS.move;
  const footP = interpolate(frame, [footStart, footStart + SYS.unit], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  return (
    <SceneShell
      title={title}
      kicker={kicker}
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      caption={caption}
      source={source}
    >
      <div
        style={{
          position: "absolute",
          left: LAYOUT.left + 48,
          right: LAYOUT.left + 48,
          top: "54%",
          transform: "translateY(-50%)",
        }}
      >
        {items.map((it, i) => {
          const start = at * fps + stagger(i);
          const p = interpolate(frame, [start, start + SYS.move], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(...EXPO_OUT),
          });
          // percentages, not pixels: the bar lives inside its flex column, so
          // the longest bar can never run under the figure beside it
          const pct = (it.value / max) * 100 * p;
          const col = it.hero ? SYS.accent : SYS.muted;

          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 28,
                marginBottom: i === items.length - 1 ? 0 : 38,
              }}
            >
              {/* label column, right-aligned so the bars share one baseline */}
              <div style={{ width: 300, flexShrink: 0, textAlign: "right" }}>
                <T
                  level="label"
                  size={TYPE.labelSm}
                  color={it.hero ? SYS.text : SYS.muted}
                  at={at}
                  index={i}
                  align="right"
                >
                  {it.label}
                </T>
                {it.note ? (
                  <T
                    level="body"
                    size={TYPE.bodySm - 3}
                    color={SYS.faint}
                    at={at}
                    index={i}
                    align="right"
                    noRise
                    style={{ marginTop: 5 }}
                  >
                    {it.note}
                  </T>
                ) : null}
              </div>

              {/* the bar: one rectangle, no rounding, no gradient */}
              <div style={{ flex: 1, position: "relative", height: it.hero ? 26 : 18 }}>
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    height: "100%",
                    width: "100%",
                    borderBottom: `1px solid ${SYS.rule}`,
                    opacity: 0.55,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    height: "100%",
                    width: `${pct}%`,
                    background: col,
                    opacity: it.hero ? 0.95 : 0.55,
                  }}
                />
                {it.hero ? (
                  <div
                    style={{
                      position: "absolute",
                      left: `${pct}%`,
                      top: -9,
                      width: 1,
                      height: "calc(100% + 18px)",
                      background: SYS.accent,
                      opacity: p,
                    }}
                  />
                ) : null}
              </div>

              {/* the number, tabular so digits never dance */}
              <div style={{ width: 150, flexShrink: 0, textAlign: "right" }}>
                <CountUp
                  to={it.value}
                  at={at + stagger(i) / fps}
                  decimals={decimals}
                  size={it.hero ? TYPE.data : TYPE.dataSm}
                  color={it.hero ? SYS.text : SYS.muted}
                />
              </div>
            </div>
          );
        })}

        <div
          style={{
            marginTop: 46,
            paddingTop: 18,
            borderTop: `1px solid ${SYS.rule}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            opacity: footP,
          }}
        >
          <span
            style={{
              fontFamily: SYS.body,
              fontSize: TYPE.bodySm,
              color: SYS.muted,
              maxWidth: 1100,
            }}
          >
            {footnote ?? " "}
          </span>
          <span
            style={{
              fontFamily: SYS.data,
              fontSize: TYPE.dataSm - 2,
              color: SYS.faint,
              letterSpacing: TRACK,
              textTransform: "uppercase",
            }}
          >
            {unit}
          </span>
        </div>
      </div>
    </SceneShell>
  );
};
