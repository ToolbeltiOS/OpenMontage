import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, EXPO_IN_OUT, LAYOUT, stagger } from "../design/system";
import { Plate, Graded, FrameLayer } from "../design/Frame";
import { T } from "../design/Type";
import { useBackdrop } from "../design/useBackdrop";

export interface ActTitleCardProps {
  /** Roman or arabic, as written: "ACT II" */
  act: string;
  title: string;
  /** one line, the act's question — not a summary */
  epigraph?: string;
  /** optional treated backdrop; without it the card is a lit void */
  image?: string;
  /** seconds; the card fades out over the last `fade_out` of its duration */
  fade_in?: number;
  fade_out?: number;
}

/**
 * The act boundary. The playbook fades through black at every act change and
 * the music crossfades over 2.5s; this card lives inside that fade, so it
 * carries its own in/out ramps rather than relying on the edit.
 *
 * No persistent chrome: the act card is the one place the dossier furniture
 * steps aside, which is what makes it read as a chapter break.
 */
export const ActTitleCard: React.FC<ActTitleCardProps> = ({
  act,
  title,
  epigraph,
  image,
  fade_in = 0.8,
  fade_out = 1.0,
}) => {
  const frame = useCurrentFrame();
  useBackdrop(image);
  const { fps, durationInFrames } = useVideoConfig();

  const inP = interpolate(frame, [0, fade_in * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });
  const outP = interpolate(
    frame,
    [durationInFrames - fade_out * fps, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(...EXPO_IN_OUT) },
  );
  const o = Math.min(inP, outP);

  // the slowest move in the film: the backdrop barely breathes
  const scale = interpolate(frame, [0, durationInFrames], [1.02, 1.07], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  const ruleStart = stagger(2) + SYS.unit;
  const ruleP = interpolate(frame, [ruleStart, ruleStart + SYS.move * 1.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ opacity: o }}>
        <AbsoluteFill style={{ transform: `scale(${scale})` }}>
          {image ? (
            <Graded strength={1.25} act={act}>
              <AbsoluteFill
                style={{
                  backgroundImage: `url(${image})`,
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                  filter: "brightness(0.46) saturate(0.6)",
                }}
              />
            </Graded>
          ) : (
            /*
             * `sweep`, for the same reason every other flat-plate scene has
             * it. Without an image this Plate is two very soft radial
             * gradients, and the 1.02 -> 1.07 breath above is a transform on
             * something with almost no contrast in it: `Plate`'s own
             * docstring measures that at about a hundredth of a grey level,
             * under the floor the freeze check uses. Measured on king-tut,
             * all four act cards held a frozen picture for 5.3 to 6.4
             * seconds of a 6.0 to 6.6 second card.
             */
            <Plate sweep />
          )}
        </AbsoluteFill>

        {/* the type sits in a pool of dark so it holds over any plate */}
        <AbsoluteFill
          style={{
            background: `linear-gradient(100deg, rgba(12,12,14,0.92) 0%, rgba(12,12,14,0.72) 46%, rgba(12,12,14,0.28) 100%)`,
          }}
        />

        <div
          style={{
            position: "absolute",
            left: LAYOUT.left + 40,
            top: "50%",
            transform: "translateY(-50%)",
            maxWidth: 1180,
          }}
        >
          <T level="data" size={TYPE.data} color={SYS.accent} at={0} index={0} style={{ letterSpacing: TRACK }}>
            {act}
          </T>

          <div
            style={{
              marginTop: 22,
              width: 160 + (LAYOUT.ruleWidth - 160) * ruleP,
              height: 1,
              background: SYS.accentDim,
            }}
          />

          <T level="display" size={TYPE.displayXL} at={0.25} index={0} style={{ marginTop: 30 }}>
            {title}
          </T>

          {epigraph ? (
            <T
              level="body"
              size={TYPE.body}
              color={SYS.muted}
              at={0.55}
              index={0}
              style={{ marginTop: 28, maxWidth: 820, lineHeight: 1.5 }}
            >
              {epigraph}
            </T>
          ) : null}
        </div>

        {/* grain and vignette only — no frame, no data strip */}
        <FrameLayer hairline={false} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
