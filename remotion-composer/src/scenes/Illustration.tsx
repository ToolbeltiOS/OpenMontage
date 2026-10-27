import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_IN_OUT } from "../design/system";
import { SceneShell } from "../design/Scene";
import { Graded } from "../design/Frame";
import { TYPE_CLASS } from "../design/layers";
import { resolveAsset } from "../lib/resolveAsset";

export interface IllustrationProps {
  /** the generated plate */
  image: string;
  /** what it depicts, as the strip will read it */
  subject: string;
  parallax?: boolean;
  parallaxFrom?: number;
  parallaxTo?: number;
  caption?: string;
  source?: string;
  title?: string;
  kicker?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
}

/**
 * A scene nobody photographed.
 *
 * The film is otherwise made of pictures someone took of something that
 * exists. This is the one kind that is not, and the whole design of it is
 * about making that impossible to miss:
 *
 *   - The style is a fixed engraving, set in `lib/illustration_spec.py` and
 *     not chosen per shot, so an illustration never arrives looking like a
 *     photograph.
 *   - The strip reads ILLUSTRATION — <subject> FOR THE WHOLE HOLD. It does
 *     not fade in at 0.6s and out at 3s like a caption, because a label
 *     that leaves before the shot does is a label the viewer can miss, and
 *     the one thing this shot must communicate is what kind of picture it
 *     is.
 *   - It goes through the same grade as every other plate, so it belongs to
 *     the film visually while being marked as made.
 *
 * `lib/illustration_spec.py` refuses this scene type for any slot tagged
 * `evidence` or `stills_of_record`.
 */
export const Illustration: React.FC<IllustrationProps> = ({
  image,
  subject,
  parallax = true,
  parallaxFrom = 1.0,
  parallaxTo = 1.05,
  caption,
  source,
  title,
  kicker,
  actNumber,
  actTitle,
  sceneIndex,
  coords,
}) => {
  const frame = useCurrentFrame();
  const { width, durationInFrames } = useVideoConfig();

  const scale = parallax
    ? interpolate(frame, [0, durationInFrames], [parallaxFrom, parallaxTo], {
        extrapolateRight: "clamp",
        easing: Easing.bezier(...EXPO_IN_OUT),
      })
    : 1;

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
        <Graded act={actNumber}>
          <Img
            src={resolveAsset(image)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </Graded>
      </AbsoluteFill>

      {/* No opacity ramp and no `at`: this is on from the first frame to the
          last. Every other label in the film earns its entrance; this one is
          a disclosure. */}
      <div
        className={TYPE_CLASS}
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 0,
          display: "flex",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            marginTop: 26,
            padding: "7px 18px",
            background: "rgba(12,12,14,0.74)",
            borderBottom: `1px solid ${SYS.accent}`,
            color: SYS.accent,
            fontFamily: SYS.label,
            fontWeight: 500,
            fontSize: TYPE.labelSm - 2,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            maxWidth: width * 0.7,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {`Illustration — ${subject}`}
        </div>
      </div>
    </SceneShell>
  );
};
