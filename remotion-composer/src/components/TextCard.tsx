import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { TYPE_CLASS } from "../design/layers";
import { PlateSweep } from "../design/Frame";

interface TextCardProps {
  text: string;
  fontSize?: number;
  color?: string;
  backgroundColor?: string;
  /**
   * The slow sustaining move under the card, as `SceneShell` gives every
   * authored scene. On by default, and for the same reason: a card that stops
   * moving when its spring settles is a frozen frame, and nothing downstream
   * can tell a frozen frame from a dropped one.
   *
   * A flat-background scene has no plate to drift, so it takes the light
   * sweep on its own — the identical branch `SceneShell` takes when it is
   * handed a `background`.
   */
  sustain?: boolean;
}

/**
 * A full-frame line of authored type.
 *
 * THE TEXT CARRIES `TYPE_CLASS`. The film renders in two passes — plate and
 * type — split by that class, and a text element that nobody marked is
 * simply still there in the plate: graded, grained, its glyph edges taking
 * the look's chromatic offset, and drifting with the picture under locked
 * type saying the same words. On king-tut that is exactly what happened to
 * all seven of these cards plus all seven stat cards: 119 words legible in
 * the plate pass, and the fringing is visible by eye on 'Four cases. One of
 * them closes.' The class costs nothing outside the two layer passes, where
 * it is the whole mechanism.
 */
export const TextCard: React.FC<TextCardProps> = ({
  text,
  fontSize = 64,
  color = "#FFFFFF",
  backgroundColor = "#1F2937",
  sustain = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = spring({ frame, fps, config: { damping: 20 } });
  const scale = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 100 },
    from: 0.95,
    to: 1,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: backgroundColor,
      }}
    >
      {sustain ? <PlateSweep /> : null}
      <div
        className={TYPE_CLASS}
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize,
          color,
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 700,
          textAlign: "center",
          maxWidth: "80%",
          lineHeight: 1.3,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
