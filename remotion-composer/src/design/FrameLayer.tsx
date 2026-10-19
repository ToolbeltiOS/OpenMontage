import React from "react";
import { FrameLayer as Frame } from "./Frame";

export interface FrameLayerAdapterProps {
  /** top-left data strip */
  topLeft?: string;
  /** bottom-right data strip */
  bottomRight?: string;
  /** 0 disables; any other number uses the system's grain density */
  grain?: number;
  vignette?: number;
  lightLeak?: boolean;
  hairline?: boolean;
  /**
   * Where the channel mark sits. "top-right" keeps the bottom fifth of the
   * frame clear, which an end card needs because YouTube draws End Screen
   * elements over it.
   */
  channelPosition?: "bottom-right" | "top-right";
}

/**
 * Adapter for components written against a `topLeft` / `bottomRight` frame.
 *
 * The design system's FrameLayer names its strips after what the documentary
 * puts in them (act number, act title, scene index), which is the right name
 * inside the film and the wrong name for a component that just wants two
 * corners. This maps one onto the other so neither has to bend.
 */
export const FrameLayer: React.FC<FrameLayerAdapterProps> = ({
  topLeft,
  bottomRight,
  grain = 1,
  vignette = 1,
  lightLeak = false,
  hairline = true,
  channelPosition = "bottom-right",
}) => (
  <Frame
    actTitle={topLeft}
    sceneIndex={channelPosition === "bottom-right" ? bottomRight : undefined}
    topRight={channelPosition === "top-right" ? bottomRight : undefined}
    grain={grain > 0}
    vignette={vignette > 0}
    hairline={hairline}
    sweepAt={lightLeak ? 0.6 : null}
  />
);
