import React from "react";
import { AbsoluteFill } from "remotion";
import { SceneRenderer, Cut } from "./Explainer";
import { DEFAULT_THEME } from "./Root";

export interface SlotPreviewProps {
  [key: string]: unknown;
  /** one cut from edit_decisions.json, passed verbatim via --props */
  cut: Cut;
}

/**
 * Renders exactly one cut, with nothing around it.
 *
 * This exists for the authoring review pass: every annotated_still and
 * schematic gets a one-frame PNG through this composition and is looked at
 * before the slot is accepted. Label collisions and anchors that have drifted
 * off their subject are invisible in a props file and obvious in a picture.
 */
export const SlotPreview: React.FC<SlotPreviewProps> = ({ cut }) => (
  <AbsoluteFill style={{ backgroundColor: "#0C0C0E" }}>
    <SceneRenderer cut={cut} theme={DEFAULT_THEME} />
  </AbsoluteFill>
);
