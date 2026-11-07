import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { TYPE_CLASS } from "../design/layers";
import { PlateSweep } from "../design/Frame";

interface StatCardProps {
  stat: string;
  subtitle?: string;
  statFontSize?: number;
  subtitleFontSize?: number;
  color?: string;
  accentColor?: string;
  backgroundColor?: string;
  /**
   * The slow sustaining move under the card — see `TextCard`. On by default:
   * c066's stat card sat on 149 byte-identical plate frames, 5.0 seconds,
   * because both of its springs settle in the first second and nothing else
   * in the frame moves.
   */
  sustain?: boolean;
}

/**
 * A full-frame figure and its subtitle.
 *
 * BOTH TEXT NODES CARRY `TYPE_CLASS` — see `TextCard` for why. The stat is
 * the one piece of type in the film a viewer is most likely to read twice.
 */

export const StatCard: React.FC<StatCardProps> = ({
  stat,
  subtitle,
  statFontSize = 128,
  subtitleFontSize = 36,
  color = "#FFFFFF",
  accentColor = "#F59E0B",
  backgroundColor = "#1F2937",
  sustain = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 120 },
    from: 0.8,
    to: 1,
  });

  const subtitleOpacity = spring({
    frame: frame - 8,
    fps,
    config: { damping: 20 },
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
      <div style={{ textAlign: "center" }}>
        <div
          className={TYPE_CLASS}
          style={{
            transform: `scale(${scale})`,
            fontSize: statFontSize,
            color: accentColor,
            fontFamily: "Inter, system-ui, sans-serif",
            fontWeight: 800,
            lineHeight: 1.1,
          }}
        >
          {stat}
        </div>
        {subtitle && (
          <div
            className={TYPE_CLASS}
            style={{
              opacity: subtitleOpacity,
              fontSize: subtitleFontSize,
              color,
              fontFamily: "Inter, system-ui, sans-serif",
              fontWeight: 400,
              marginTop: 16,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
