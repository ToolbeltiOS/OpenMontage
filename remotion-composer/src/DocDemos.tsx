import React from "react";
import { staticFile } from "remotion";
import { AnnotatedStill } from "./components/AnnotatedStill";
import { Schematic } from "./components/Schematic";
import { MapRoute } from "./components/MapRoute";
import { GlobeDescent } from "./components/GlobeDescent";
import { Timeline } from "./components/Timeline";
import { DocumentReveal } from "./components/DocumentReveal";
import { SYS } from "./design/system";

/* ───────────────────────── component demos (5s each) ───────────────────── */

export const DemoAnnotatedStill: React.FC = () => (
  <AnnotatedStill
    image={staticFile("doc/aswan_quarry.jpg")}
    parallax
    actNumber="03"
    actTitle="The hole in the granite"
    sceneIndex="S 112 / ASWAN"
    coords="24.0889° N  32.8998° E"
    annotations={[
      { label: "dolerite pounder", x: 0.605, y: 0.645, reveal_at: 0.6, side: "left" },
      { label: "worked surface", x: 0.33, y: 0.52, reveal_at: 1.8, side: "right" },
    ]}
    measurement={{ text: "≈ 0.9 m", from: { x: 0.24, y: 0.82 }, to: { x: 0.46, y: 0.82 }, reveal_at: 3.0 }}
    caption="Aswan granite quarry — pounding stones in situ"
    source="Wikimedia Commons · CC BY-SA"
  />
);

export const DemoSchematic: React.FC = () => (
  <Schematic
    kicker="File 3"
    title="Khufu's Pyramid — section"
    actNumber="04"
    actTitle="The cases nobody has closed"
    sceneIndex="S 158 / GIZA"
    coords="29.9792° N  31.1342° E"
    caption="Big Void placed above the Grand Gallery"
    source="Morishima et al., Nature 552, 386–390 (2017)"
    layers={[
      { id: "ground", kind: "line", x: 260, y: 880, x2: 1660, y2: 880, stroke: SYS.rule, strokeWidth: 3 },
      { id: "outline", kind: "path", d: "M 960 190 L 1655 878 L 265 878 Z", stroke: SYS.text, strokeWidth: 3 },
      { id: "gallery", kind: "path", d: "M 790 735 L 1010 505", stroke: SYS.muted, strokeWidth: 10 },
      { id: "queen", kind: "rect", x: 735, y: 745, w: 110, h: 54, stroke: SYS.muted, strokeWidth: 3 },
      { id: "void", kind: "rect", x: 880, y: 405, w: 300, h: 66, stroke: SYS.accent, strokeWidth: 4, dashed: true },
      { id: "entry", kind: "line", x: 560, y: 690, x2: 735, y2: 772, stroke: SYS.muted, strokeWidth: 5 },
    ]}
    reveals={[
      { layer_id: "ground", at: 0.1, effect: "fade" },
      { layer_id: "outline", at: 0.35, effect: "draw", duration: 1.3 },
      { layer_id: "entry", at: 1.4, effect: "draw", duration: 0.5 },
      { layer_id: "queen", at: 1.8, effect: "fade" },
      { layer_id: "gallery", at: 2.2, effect: "draw", duration: 0.7 },
      { layer_id: "void", at: 3.2, effect: "fade" },
    ]}
    labels={[
      { text: "Grand Gallery", x: 1040, y: 560, at: 2.9 },
      { text: "Big Void — min. 30 m", x: 1222, y: 442, at: 3.6, accent: true, level: "data" },
      { text: "Queen's chamber", x: 600, y: 790, at: 2.0, anchor: "end" },
    ]}
  />
);

export const DemoMapRoute: React.FC = () => (
  <MapRoute
    kicker="Transport"
    title="The Altar Stone's journey"
    actNumber="02"
    actTitle="The statues that walked"
    sceneIndex="S 081 / ORCADIAN BASIN"
    route={[
      [-3.0, 58.6],
      [-3.6, 57.6],
      [-5.6, 55.9],
      [-5.2, 53.4],
      [-4.6, 51.9],
      [-1.826, 51.179],
    ]}
    markers={[
      { lon: -3.0, lat: 58.6, label: "Orcadian Basin", at: 0.5 },
      { lon: -1.826, lat: 51.179, label: "Stonehenge", at: 2.9, dx: 20, dy: 28 },
    ]}
    scale={1500}
    basemap={{ src: "basemaps/orcadian.jpg", bounds: [-42.5, 39.5, 34.5, 66.5] }}
    draw_at={0.9}
    draw_seconds={2.4}
    distance_callout={{ text: "≥ 750 km", at: 3.5 }}
    caption="A sea route is the likelier explanation"
    source="Clarke et al., Nature 632 (2024)"
  />
);

export const DemoTimeline: React.FC = () => (
  <Timeline
    kicker="Chronology"
    title="Who was looking, and when"
    actNumber="01"
    actTitle="A verdict two thousand years old"
    sceneIndex="S 034 / TIMELINE"
    events={[
      { year: -1400, label: "Tiryns walls raised", at: 0.4 },
      { year: -1200, label: "Mycenaean world ends", at: 1.2 },
      { year: 170, label: "Pausanias records the Cyclopes", at: 2.1, accent: true },
      { year: 1922, label: "Petrie's core described", at: 3.0 },
      { year: 2017, label: "Big Void detected", at: 3.8, accent: true },
    ]}
    caption="Negative years are BC"
  />
);

export const DemoDocumentReveal: React.FC = () => (
  <DocumentReveal
    kicker="The record"
    headline="Pausanias, Description of Greece"
    actNumber="01"
    actTitle="A verdict two thousand years old"
    sceneIndex="S 041 / TIRYNS"
    lines={[
      { text: "“…the wall at Tiryns, which is made of unwrought stones,", at: 0.5 },
      { text: "every stone being so big that a pair of mules", at: 1.5 },
      { text: "could not move the smallest from its place.”", at: 2.5, emphasis: true },
    ]}
    source="Book II, 2nd century CE"
    paper="dark"
    light_sweep
    sweep_at={2.9}
  />
);

/* ───────────────────── three real slots from the film ──────────────────── */

/** act4_s171 — the owner-approved Sacsayhuamán joint crop, annotated. */
export const SlotAct4S171: React.FC = () => (
  <AnnotatedStill
    image={staticFile("doc/sacsay_joint.jpg")}
    parallax
    actNumber="04"
    actTitle="The cases nobody has closed"
    sceneIndex="S 171 / SACSAYHUAMÁN"
    coords="13.5095° S  71.9817° W"
    annotations={[
      { label: "contact line", x: 0.42, y: 0.46, reveal_at: 0.7 },
      { label: "no mortar", x: 0.72, y: 0.3, reveal_at: 2.2, side: "left" },
    ]}
    caption="Sacsayhuamán, Cusco"
    source="Diego Delso · CC BY-SA 4.0"
  />
);

/** act3_s110 — the carrier mechanism: copper holds, sand cuts. */
export const SlotAct3S110: React.FC = () => (
  <Schematic
    kicker="Mechanism"
    title="The carrier mechanism"
    actNumber="03"
    actTitle="The hole in the granite"
    sceneIndex="S 110 / TUBE DRILL"
    caption="Copper does not cut — the abrasive does"
    source="After Stocks, experimental archaeology"
    viewBox="0 0 1920 1080"
    layers={[
      { id: "stone", kind: "rect", x: 460, y: 560, w: 1000, h: 330, stroke: SYS.muted, fill: "#17171C", strokeWidth: 3 },
      { id: "kerf", kind: "rect", x: 880, y: 560, w: 160, h: 220, stroke: SYS.rule, fill: SYS.bg, strokeWidth: 2 },
      { id: "tubeL", kind: "line", x: 880, y: 250, x2: 880, y2: 775, stroke: SYS.accent, strokeWidth: 7 },
      { id: "tubeR", kind: "line", x: 1040, y: 250, x2: 1040, y2: 775, stroke: SYS.accent, strokeWidth: 7 },
      { id: "core", kind: "rect", x: 902, y: 600, w: 116, h: 290, stroke: SYS.text, strokeWidth: 2, dashed: true },
      { id: "sand1", kind: "circle", x: 892, y: 740, r: 7, fill: SYS.text, stroke: "none" },
      { id: "sand2", kind: "circle", x: 1030, y: 700, r: 6, fill: SYS.text, stroke: "none" },
      { id: "sand3", kind: "circle", x: 893, y: 660, r: 5, fill: SYS.text, stroke: "none" },
      { id: "rot", kind: "path", d: "M 836 214 a 124 44 0 1 0 248 0", stroke: SYS.muted, strokeWidth: 3 },
    ]}
    reveals={[
      { layer_id: "stone", at: 0.1, effect: "fade" },
      { layer_id: "tubeL", at: 0.6, effect: "draw", duration: 0.6 },
      { layer_id: "tubeR", at: 0.6, effect: "draw", duration: 0.6 },
      { layer_id: "kerf", at: 1.3, effect: "fade" },
      { layer_id: "core", at: 1.8, effect: "fade" },
      { layer_id: "sand1", at: 2.3, effect: "fade" },
      { layer_id: "sand2", at: 2.5, effect: "fade" },
      { layer_id: "sand3", at: 2.7, effect: "fade" },
      { layer_id: "rot", at: 3.2, effect: "draw", duration: 0.8 },
    ]}
    labels={[
      { text: "copper tube (carrier)", x: 1105, y: 320, at: 1.1, accent: true },
      { text: "quartz sand (cuts)", x: 1105, y: 700, at: 2.9, accent: true },
      { text: "core", x: 830, y: 980, at: 2.0, anchor: "end" },
    ]}
  />
);

/** act2_s078 — Preseli to Salisbury Plain, the bluestone route. */
export const SlotAct2S078: React.FC = () => (
  <MapRoute
    kicker="Transport"
    title="Preseli to Salisbury Plain"
    actNumber="02"
    actTitle="The statues that walked"
    sceneIndex="S 078 / PRESELI"
    route={[
      [-4.74, 51.99],
      [-4.1, 51.78],
      [-3.2, 51.5],
      [-2.4, 51.3],
      [-1.826, 51.179],
    ]}
    markers={[
      { lon: -4.74, lat: 51.99, label: "Carn Goedog", at: 0.5 },
      { lon: -1.826, lat: 51.179, label: "Stonehenge", at: 2.8, dx: 18, dy: 30 },
    ]}
    scale={5200}
    draw_at={0.9}
    draw_seconds={2.2}
    distance_callout={{ text: "140 or 180 miles?", at: 3.4 }}
    caption="Institutions publish different figures for the same journey"
  />
);


/**
 * Preseli to Salisbury Plain over the terrain base — the second of the two
 * test routes for the cinematic map. The hills the bluestone came from are
 * visible as hills here; on the flat plate they were an undifferentiated grey
 * silhouette.
 */
export const DemoMapRoutePreseli: React.FC = () => (
  <MapRoute
    kicker="Transport"
    title="Preseli to Salisbury Plain"
    actNumber="02"
    actTitle="Where the stones came from"
    sceneIndex="S 069 / PRESELI"
    route={[
      [-4.74, 51.99],
      [-4.1, 51.78],
      [-3.2, 51.5],
      [-2.4, 51.3],
      [-1.826, 51.179],
    ]}
    markers={[
      { lon: -4.74, lat: 51.99, label: "Carn Goedog", at: 0.5 },
      { lon: -1.826, lat: 51.179, label: "Stonehenge", at: 2.6, dx: 18, dy: 26 },
    ]}
    scale={5200}
    basemap={{ src: "basemaps/preseli.jpg", bounds: [-15.5, 46.2, 9.0, 56.6] }}
    draw_at={0.8}
    draw_seconds={2.2}
    distance_callout={{ text: "≈ 225 km", at: 3.2 }}
    caption="Carn Goedog and Craig Rhos-y-felin to Salisbury Plain"
    source="Parker Pearson et al., Antiquity 93 (2019)"
  />
);


/**
 * The globe descent, handing off to the Orcadian route. The map it dissolves
 * into is the same component with the same extent, so the handoff lands on
 * the geography the descent was aiming at rather than cutting to another
 * drawing of it.
 */
export const DemoGlobeDescent: React.FC = () => (
  <GlobeDescent lon={-3.9} lat={55.5} seconds={3.5}>
    <DemoMapRoute />
  </GlobeDescent>
);
