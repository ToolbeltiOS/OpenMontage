/**
 * wak3up-documentary DESIGN SYSTEM
 *
 * Motion-language spec, locked per `motion-art-direction`. One choice per row;
 * everything in the film obeys it. Consistency reads as confidence.
 *
 *   Tone & energy      CALM + SHARP  (archival forensic dossier)
 *   Easing family      expo-out for entrances, expo-in-out for moves. No linear.
 *   Base timing unit   12 frames @30fps (0.4s). micro 6f, enter 12f, move 24f.
 *   Transition family  cut / dissolve / fade-to-black / grain-leak (hero only)
 *   Stagger rhythm     3 frames per element
 *   Motion intensity   rise 8px, parallax 1.0→1.08, overshoot 0 (schematic draw excepted)
 *   Hold discipline    ≥ 9 frames of stillness after each beat
 *
 * Motion hierarchy: Hero (the one thing the shot is about) / Support (context)
 * / Texture (grain, drift — subliminal only).
 */

import { FAMILIES } from "./fonts";

export const SYS = {
  // ── palette: 1 primary + 1 accent + neutrals ────────────────────────────
  bg: "#0C0C0E",
  plate: "#101014",
  surface: "#14141A",
  text: "#EDE6D8",
  muted: "#8A8578",
  faint: "#55514A",
  accent: "#C08A3E",
  accentDim: "#8A6A3B",
  rule: "#3A3630",
  paper: "#E8DFC9",
  paperInk: "#241F18",

  // ── type levels: four, and nothing else ─────────────────────────────────
  display: FAMILIES.display,
  label: FAMILIES.sans,
  data: FAMILIES.mono,
  body: FAMILIES.sans,

  // ── timing ──────────────────────────────────────────────────────────────
  unit: 12,          // frames; the atomic duration
  micro: 6,
  move: 24,
  stagger: 3,        // frames between grouped elements
  hold: 9,           // minimum stillness after a beat
  rise: 8,           // px
  blurFrom: 6,       // px, blur-to-sharp entrance
} as const;

/** Entrances and landings. expo-out. */
export const EXPO_OUT = [0.16, 1, 0.3, 1] as const;
/** Moves that start and stop. expo-in-out. */
export const EXPO_IN_OUT = [0.87, 0, 0.13, 1] as const;

/** Type ramp. Nothing outside these sizes. */
export const TYPE = {
  displayXL: 86,
  display: 64,
  displaySm: 42,
  label: 28,
  labelSm: 22,
  data: 26,
  dataSm: 20,
  body: 24,
  bodySm: 19,
} as const;

/**
 * Chrome shadow. The persistent frame has to sit on a black plate and on a
 * sunlit granite photograph without changing colour, so every chrome element
 * carries this. Without it the data strip vanishes over a bright still.
 */
export const SHADOW = "0 1px 10px rgba(0,0,0,0.85), 0 0 3px rgba(0,0,0,0.95)";

/** Letterspacing for the caps Label level. */
export const TRACK = "0.16em";

/** Unified grade applied to every still and clip. */
export const GRADE = {
  /** lifted blacks toward the film's own background */
  lift: SYS.bg,
  saturation: 0.86,
  contrast: 1.04,
  warmHighlights: "rgba(192,138,62,0.10)",
  coolShadows: "rgba(38,52,74,0.16)",
  grainOpacity: 0.055,
  vignette: 0.34,
  chromatic: 0.5, // px
} as const;

/**
 * One margin for the whole film. Every scene's chrome aligns to it, so cutting
 * between an annotated still and a schematic never shifts the furniture.
 */
export const LAYOUT = {
  /** hairline frame inset */
  frameInset: 54,
  /** text gutter inside the frame */
  left: 82,
  top: 62,
  bottom: 62,
  /** width of the rule under a scene title */
  ruleWidth: 300,
} as const;

/**
 * Grouped view of the same tokens, for components written against a
 * `tokens.color` / `tokens.font` shape. One source of truth — these are the
 * values above, not a second palette.
 */
export const tokens = {
  color: {
    bg: SYS.bg,
    ink: SYS.text,
    accent: SYS.accent,
    /** text sitting ON the accent, where the ochre is the fill */
    accentInk: "#14100A",
    muted: SYS.muted,
    rule: SYS.rule,
  },
  font: {
    display: SYS.display,
    label: SYS.label,
    data: SYS.data,
    body: SYS.body,
  },
} as const;

/** Stagger helper: nth element enters this many frames late. */
export const stagger = (n: number) => n * SYS.stagger;
