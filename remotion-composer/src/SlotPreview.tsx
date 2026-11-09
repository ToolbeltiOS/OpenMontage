import React from "react";
import { AbsoluteFill } from "remotion";
import { SceneRenderer, Cut } from "./Explainer";
import { DEFAULT_THEME } from "./Root";
import { LayerMode, LayerScope } from "./design/layers";

export interface SlotPreviewProps {
  [key: string]: unknown;
  /** one cut from edit_decisions.json, passed verbatim via --props */
  cut: Cut;
  /**
   * Which layer to draw, exactly as the film render asks for it.
   *
   * Without this a style frame could not be gated. `plate_is_clean` reads
   * the PLATE pass and fails on any word legible in it; handed a full
   * render it finds the type it is looking for and reports every scene as
   * dirty, which is a gate measuring the wrong file rather than a finding.
   */
  layer_mode?: LayerMode;
}

/**
 * Renders exactly one cut, with nothing around it.
 *
 * This exists for the authoring review pass: every annotated_still and
 * schematic gets a one-frame PNG through this composition and is looked at
 * before the slot is accepted. Label collisions and anchors that have drifted
 * off their subject are invisible in a props file and obvious in a picture.
 */
export const SlotPreview: React.FC<SlotPreviewProps> = ({ cut, layer_mode }) => (
  <AbsoluteFill
    style={{
      backgroundColor: layer_mode === "type" ? "transparent" : "#0C0C0E",
    }}
  >
    <LayerScope mode={layer_mode ?? "all"}>
      <SceneRenderer cut={cut} theme={DEFAULT_THEME} />
    </LayerScope>
  </AbsoluteFill>
);
