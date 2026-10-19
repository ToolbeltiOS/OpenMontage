import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, EXPO_IN_OUT, LAYOUT, SHADOW } from "../design/system";
import { FrameLayer, Plate } from "../design/Frame";
import { T } from "../design/Type";

export interface OutroCtaProps {
  /** the film's title, set in the dimmed title-card treatment behind the CTA */
  title: string;
  kicker?: string;
  /** seconds, from scene start, when the narration says "like" */
  like_at: number;
  /** seconds, from scene start, when the narration says "subscribe" */
  subscribe_at: number;
  subscribe_label?: string;
  sceneIndex?: string;
  actNumber?: string;
  actTitle?: string;
}

/* Icons are drawn, not imported: no platform marks, no platform colours. */
const THUMB =
  "M 20 46 L 20 88 L 38 88 L 38 46 Z " +
  "M 42 88 L 76 88 C 85 88 90 81 88 73 L 82 52 C 80 46 76 44 70 44 L 55 44 " +
  "L 59 26 C 61 16 55 8 47 10 C 43 11 41 14 40 18 L 37 34 L 42 44 Z";
const BELL =
  "M 50 16 L 50 26 M 28 74 C 28 50 33 30 50 30 C 67 30 72 50 72 74 L 79 80 L 21 80 Z " +
  "M 42 86 a 8 8 0 0 0 16 0";
const CURSOR = "M 0 0 L 0 27 L 7 20 L 12 31 L 17 29 L 12 18 L 19 18 Z";

/** 0.9 -> 1.05 -> 1.0 over 12 frames, and the fill arrives with the press. */
const press = (frame: number, at: number, fps: number) => {
  const s = at * fps;
  const scale = interpolate(frame, [s - 4, s, s + 5, s + 12], [1, 0.9, 1.05, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });
  const fill = interpolate(frame, [s, s + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });
  return { scale, fill };
};

/**
 * The end card: the film's own title treatment, dimmed, with a drawn
 * like/subscribe beat timed to the words that ask for it.
 *
 * The right third and the bottom fifth are deliberately empty — that is where
 * YouTube places End Screen elements, and anything put there gets covered.
 */
export const OutroCta: React.FC<OutroCtaProps> = ({
  title,
  kicker = "WAK3UP",
  like_at,
  subscribe_at,
  subscribe_label = "SUBSCRIBE",
  sceneIndex = "END / WAK3UPSOCIETY",
  actNumber = "END",
  actTitle = "WAK3UPSOCIETY",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const THUMB_X = 250, THUMB_Y = 470;
  const PILL_X = 470, PILL_Y = 500, PILL_W = 330, PILL_H = 74;
  const BELL_X = 890, BELL_Y = 470;

  const thumb = press(frame, like_at, fps);
  const sub = press(frame, subscribe_at, fps);

  // the pointer travels, waits, travels again — it never drifts
  const travel = (fromX: number, fromY: number, toX: number, toY: number,
                  start: number, end: number) => {
    const p = interpolate(frame, [start * fps, end * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_IN_OUT),
    });
    return { x: fromX + (toX - fromX) * p, y: fromY + (toY - fromY) * p };
  };

  const toThumb = travel(1080, 760, THUMB_X + 54, THUMB_Y + 70, like_at - 1.1, like_at - 0.08);
  const toPill = travel(THUMB_X + 54, THUMB_Y + 70, PILL_X + PILL_W / 2, PILL_Y + PILL_H / 2,
                        like_at + 0.42, subscribe_at - 0.06);
  const cursor = frame < (like_at + 0.42) * fps ? toThumb : toPill;
  const cursorIn = interpolate(frame, [(like_at - 1.3) * fps, (like_at - 1.0) * fps], [0, 1],
                               { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // the bell rings after the word has landed, twice, and settles
  const bellStart = subscribe_at + 0.75;
  const swing = interpolate(
    frame,
    [bellStart * fps, (bellStart + 0.18) * fps, (bellStart + 0.36) * fps,
     (bellStart + 0.54) * fps, (bellStart + 0.72) * fps, (bellStart + 0.95) * fps],
    [0, -13, 11, -7, 4, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(...EXPO_OUT) },
  );
  const bellLive = frame >= bellStart * fps ? 1 : 0;

  const outP = interpolate(frame, [durationInFrames - 12, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  const stroke = SYS.text;

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg, opacity: outP }}>
      <Plate />

      {/* the title-card treatment, dimmed to 40% and left as background */}
      <div style={{ position: "absolute", left: LAYOUT.left + 40, top: LAYOUT.top + 40, opacity: 0.4 }}>
        <T level="data" size={TYPE.dataSm} color={SYS.accent} at={0} style={{ letterSpacing: TRACK }}>
          {kicker}
        </T>
        <div style={{ marginTop: 16, width: 220, height: 1, background: SYS.accentDim }} />
        <T level="display" size={TYPE.display} at={0.15} style={{ marginTop: 22, maxWidth: 980 }}>
          {title}
        </T>
      </div>

      {/* CTA row — left two thirds, clear of the bottom fifth */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        <g transform={`translate(${THUMB_X} ${THUMB_Y}) scale(${thumb.scale})`}
           style={{ transformBox: "fill-box", transformOrigin: "center" }}>
          <path d={THUMB} fill={SYS.accent} fillOpacity={thumb.fill} stroke={stroke}
                strokeWidth={3} strokeLinejoin="round" />
        </g>

        <g transform={`translate(${BELL_X} ${BELL_Y})`}>
          <g transform={`rotate(${swing} 50 20)`}>
            <path d={BELL} fill={SYS.accent} fillOpacity={bellLive * 0.9} stroke={stroke}
                  strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
          </g>
        </g>

        <rect x={PILL_X} y={PILL_Y} width={PILL_W} height={PILL_H} rx={PILL_H / 2}
              fill={SYS.accent} fillOpacity={sub.fill} stroke={stroke} strokeWidth={2.5}
              style={{ transform: `scale(${sub.scale})`, transformBox: "fill-box",
                       transformOrigin: "center" }} />

        {cursorIn > 0 ? (
          <g transform={`translate(${cursor.x} ${cursor.y})`} opacity={cursorIn}>
            <path d={CURSOR} fill={SYS.bg} stroke={stroke} strokeWidth={2.5} strokeLinejoin="round" />
          </g>
        ) : null}
      </svg>

      <div
        style={{
          position: "absolute",
          left: PILL_X,
          top: PILL_Y,
          width: PILL_W,
          height: PILL_H,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: SYS.label,
          fontWeight: 500,
          fontSize: TYPE.labelSm,
          letterSpacing: TRACK,
          color: sub.fill > 0.5 ? SYS.bg : SYS.text,
          textShadow: sub.fill > 0.5 ? undefined : SHADOW,
          pointerEvents: "none",
        }}
      >
        {subscribe_label}
      </div>

      <FrameLayer actNumber={actNumber} actTitle={actTitle} sceneIndex={sceneIndex} />
    </AbsoluteFill>
  );
};
