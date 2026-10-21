import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, EXPO_OUT, EXPO_IN_OUT, LAYOUT } from "../design/system";
import { SceneShell } from "../design/Scene";
import { resolveAsset } from "../lib/resolveAsset";
import { TYPE_CLASS } from "../design/layers";

export interface DocumentLine {
  text: string;
  at: number;
  emphasis?: boolean;
}

export interface DocumentRevealProps {
  headline?: string;
  lines: DocumentLine[];
  source?: string;
  /** optional scan to sit under the text */
  image?: string;
  paper?: "light" | "dark";
  light_sweep?: boolean;
  sweep_at?: number;
  caption?: string;
  kicker?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
}

/**
 * Paper-grain document reveal, line by line, with a raking light sweep.
 * Carries the quoted material — Pausanias, Dunn's falsification condition,
 * Stocks' concession, the geochemical finding.
 *
 * The one scene type that inverts: on light paper the persistent chrome takes
 * the paper's own ink, so the frame reads as printed on the page rather than
 * floating over it.
 */
export const DocumentReveal: React.FC<DocumentRevealProps> = ({
  headline,
  lines,
  source,
  image,
  paper = "dark",
  light_sweep = true,
  sweep_at = 0.8,
  caption,
  kicker,
  actNumber,
  actTitle,
  sceneIndex,
  coords,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, durationInFrames } = useVideoConfig();

  const light = paper === "light";
  const bg = light ? SYS.paper : "#121116";
  const ink = light ? SYS.paperInk : SYS.text;
  const emphasis = light ? "#8A5A1E" : SYS.accent;

  const appear = (at: number, frames: number = SYS.unit) =>
    interpolate(frame, [at * fps, at * fps + frames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    });

  // slow push so the plate is never a dead hold
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.045], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  const sweepP = interpolate(frame, [sweep_at * fps, (sweep_at + 2.2) * fps], [-0.4, 1.4], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  const lastAt = lines[lines.length - 1]?.at ?? 0;

  return (
    <SceneShell
      background={SYS.bg}
      paperInk={light}
      caption={caption}
      kicker={kicker}
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      coords={coords}
      grain={!light}
    >
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        <AbsoluteFill style={{ backgroundColor: bg }} />
        {image ? (
          <Img
            src={resolveAsset(image)}
            style={{ width: "100%", height: "100%", objectFit: "cover", opacity: light ? 0.3 : 0.26 }}
          />
        ) : null}

        {/* paper grain */}
        <AbsoluteFill
          style={{
            opacity: light ? 0.3 : 0.22,
            backgroundImage:
              "repeating-linear-gradient(0deg, rgba(0,0,0,0.05) 0px, rgba(0,0,0,0.05) 1px, transparent 1px, transparent 3px)",
            mixBlendMode: "multiply",
          }}
        />

        {light_sweep ? (
          <AbsoluteFill
            style={{
              background: `linear-gradient(104deg, transparent ${(sweepP - 0.22) * 100}%, rgba(255,243,214,0.16) ${
                sweepP * 100
              }%, transparent ${(sweepP + 0.22) * 100}%)`,
              mixBlendMode: "screen",
            }}
          />
        ) : null}

        <div
          style={{
            position: "absolute",
            inset: 0,
            padding: `${LAYOUT.top + 90}px ${LAYOUT.left + 78}px`,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          {headline ? (
            <div className={TYPE_CLASS}
              style={{
                opacity: appear(0.15),
                transform: `translateZ(0) translateY(${Math.round((1 - appear(0.15)) * SYS.rise)}px)`,
                color: ink,
                fontFamily: SYS.display,
                fontWeight: 600,
                fontSize: TYPE.displaySm,
                marginBottom: 38,
                letterSpacing: "-0.01em",
              }}
            >
              {headline}
            </div>
          ) : null}

          {lines.map((l, i) => {
            const o = appear(l.at);
            return (
              <div className={TYPE_CLASS}
                key={i}
                style={{
                  opacity: o,
                  filter: o < 1 ? `blur(${(1 - o) * SYS.blurFrom}px)` : undefined,
                  transform: `translateZ(0) translateY(${Math.round((1 - o) * SYS.rise)}px)`,
                  color: l.emphasis ? emphasis : ink,
                  fontFamily: SYS.display,
                  fontWeight: l.emphasis ? 600 : 400,
                  fontSize: l.emphasis ? TYPE.displaySm - 4 : TYPE.display - 26,
                  lineHeight: 1.45,
                  marginBottom: 16,
                  maxWidth: width * 0.74,
                }}
              >
                {l.text}
              </div>
            );
          })}

          {source ? (
            <div className={TYPE_CLASS}
              style={{
                opacity: appear(lastAt + 0.7),
                color: light ? "rgba(36,31,24,0.62)" : SYS.muted,
                fontFamily: SYS.data,
                fontSize: TYPE.dataSm,
                marginTop: 36,
                borderTop: `1px solid ${light ? "rgba(36,31,24,0.25)" : SYS.rule}`,
                paddingTop: 18,
                maxWidth: width * 0.6,
                letterSpacing: "0.06em",
              }}
            >
              {source}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};
