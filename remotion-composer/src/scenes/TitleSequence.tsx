import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, EXPO_IN_OUT, LAYOUT } from "../design/system";
import { Plate, Graded, FrameLayer } from "../design/Frame";
import { T } from "../design/Type";

export interface TitleSequenceProps {
  /** the film's title, as it is published */
  title: string;
  /** the channel mark, set in caps under the rule */
  channel?: string;
  /** one line above the title — the register, not a summary */
  kicker?: string;
  /** treated hero still; without one the card is a lit void */
  image?: string;
  /**
   * Seconds into the scene when the title lands. The audio stage puts the
   * sting on this same number, so the rule snapping to full width and the hit
   * are the same event. Moving one without the other is the defect this prop
   * exists to prevent.
   */
  sting_at?: number;
  fade_in?: number;
  fade_out?: number;
}

/**
 * The film's title card, placed immediately after the cold open.
 *
 * It is not an act card. The act card is a chapter break inside a film that is
 * already running; this one has to start the film, so it holds longer, the
 * type is larger, and one accent event — the rule reaching full width — lands
 * on the sting rather than drifting in with everything else.
 *
 * Like the act card it drops the dossier furniture: the persistent frame
 * returns on the first scene after it, and its absence here is what makes the
 * film look like it has begun.
 */
export const TitleSequence: React.FC<TitleSequenceProps> = ({
  title,
  channel = "WAK3UPSOCIETY",
  kicker,
  image,
  sting_at = 1.8,
  fade_in = 0.7,
  fade_out = 0.9,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;

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

  // The push runs the whole card and never stops, so the still is still moving
  // when the cut takes it — the motion belongs to the film, not to the card.
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.06], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  // The one accent event. 0.34s of travel, expo-out, landing on sting_at.
  const sting = interpolate(t, [sting_at - 0.34, sting_at], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });
  // A single frame-and-a-half of lift as it lands, then gone. Any longer and
  // it reads as a flash transition, which the playbook forbids.
  const lift = interpolate(t, [sting_at, sting_at + 0.05, sting_at + 0.5], [0, 0.1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ opacity: o }}>
        <AbsoluteFill style={{ transform: `scale(${scale})` }}>
          {image ? (
            <Graded strength={1.15}>
              <AbsoluteFill
                style={{
                  backgroundImage: `url(${image})`,
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                  filter: "brightness(0.52) saturate(0.62)",
                }}
              />
            </Graded>
          ) : (
            <Plate />
          )}
        </AbsoluteFill>

        {/* the title sits in its own pool of dark, bottom-weighted */}
        <AbsoluteFill
          style={{
            background:
              "linear-gradient(180deg, rgba(12,12,14,0.55) 0%, rgba(12,12,14,0.25) 38%, rgba(12,12,14,0.88) 100%)",
          }}
        />

        <div
          style={{
            position: "absolute",
            left: LAYOUT.left + 40,
            right: LAYOUT.left + 40,
            bottom: 150,
          }}
        >
          {kicker ? (
            <T
              level="label"
              size={TYPE.labelSm}
              color={SYS.muted}
              at={0.3}
              index={0}
              style={{ letterSpacing: TRACK, marginBottom: 26 }}
            >
              {kicker}
            </T>
          ) : null}

          <T level="display" size={TYPE.displayXL} at={0.5} index={0} style={{ maxWidth: 1480 }}>
            {title}
          </T>

          {/* the sting: a rule that reaches full width on the hit */}
          <div
            style={{
              marginTop: 34,
              width: 120 + (LAYOUT.ruleWidth * 2 - 120) * sting,
              height: 1,
              background: SYS.accent,
              opacity: 0.4 + 0.6 * sting,
            }}
          />

          <T
            level="label"
            size={TYPE.labelSm}
            color={SYS.text}
            at={sting_at + 0.15}
            index={0}
            style={{ letterSpacing: TRACK, marginTop: 22, opacity: 0.74 }}
          >
            {channel}
          </T>
        </div>

        <AbsoluteFill style={{ background: SYS.text, opacity: lift, pointerEvents: "none" }} />

        {/* grain and vignette only — the frame returns on the next scene */}
        <FrameLayer hairline={false} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default TitleSequence;
