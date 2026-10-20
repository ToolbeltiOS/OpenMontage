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

/**
 * PER-ACT GRADE.
 *
 * One uniform grade across the film makes a cut between a 1890s plate and a
 * modern photograph stop announcing its source — that is what GRADE above is
 * for, and it stays. What it cannot do is let an act have a temperature of
 * its own, so run #1's four acts looked identical even though they are set on
 * a Greek ridge, a Pacific island, an Egyptian quarry and four unresolved
 * sites.
 *
 * These are offsets on top of the base grade, not replacements: the film's
 * look is still one look. They apply to PHOTOGRAPHIC material only —
 * stills, footage, treated plates. Authored graphics keep the base palette,
 * because an ochre rule that shifts warm in act 3 reads as a rendering bug,
 * and they get it structurally: a schematic or a timeline is never wrapped in
 * <Graded>.
 *
 * `temperature` is the opacity of a warm wash; negative is the cool one.
 */
export type ActGrade = {
  temperature: number;
  saturation: number;
  lift: number;
};

export const GRADE_BY_ACT: Record<string, ActGrade> = {
  // Rapa Nui at the edge of the Pacific — cool, open, the least saturated
  cold_open: { temperature: -0.05, saturation: 0.80, lift: 0.07 },
  // Tiryns and Mycenae: dry stone on a Greek ridge, close to the base look
  act1: { temperature: 0.02, saturation: 0.88, lift: 0.05 },
  // the quarry and the sea route — cooler again, and the flattest
  act2: { temperature: -0.04, saturation: 0.82, lift: 0.06 },
  // Aswan granite under an Egyptian sun: the warmest act in the film
  act3: { temperature: 0.08, saturation: 0.90, lift: 0.04 },
  // the cases nobody has closed; the film drops here and ends almost quiet
  act4: { temperature: -0.02, saturation: 0.78, lift: 0.09 },
  outro: { temperature: 0.03, saturation: 0.86, lift: 0.05 },
};

export const BASE_ACT_GRADE: ActGrade = {
  temperature: 0,
  saturation: GRADE.saturation,
  lift: 0.05,
};

/**
 * The grade for an act, by section id ("act2") or by the chrome's act number
 * ("02"). The keys match the playbook's `visual_language.grade_by_act`
 * exactly, so the two tables can be compared by a test instead of by eye.
 */
export const gradeForAct = (act?: string | number): ActGrade => {
  if (act === undefined || act === null) return BASE_ACT_GRADE;
  let key = String(act).trim().toLowerCase();
  if (/^\d+$/.test(key)) key = `act${parseInt(key, 10)}`;
  return GRADE_BY_ACT[key] ?? BASE_ACT_GRADE;
};

/**
 * The grade as a set of OPERATIONS, identical on both render paths.
 *
 * The CSS treatment and the shader pass were applying the same table by
 * different arithmetic — a flat darkening wash on one side, an additive
 * BrightnessContrast on the other — so the two differed in exposure before
 * they differed in anything that mattered. A comparison of two exposures is
 * not a comparison of two looks.
 *
 * Both paths now run the same chain: multiply by `multiply` x `brightness`,
 * then saturate, then contrast. CSS does it with a filter plus a
 * multiply-blended layer; the shader does it with the plane's material colour
 * plus HueSaturation and BrightnessContrast. Same numbers, same order.
 */
export const BRIGHTNESS_PULL = 0.85;
export const WARM_TINT = [1.0, 0.955, 0.885] as const;
export const COOL_TINT = [0.925, 0.955, 1.0] as const;

export type GradeOps = {
  saturation: number;
  contrast: number;
  brightness: number;
  /** linear multiply applied before saturation and contrast */
  multiply: [number, number, number];
};

export const gradeOps = (act?: string | number): GradeOps => {
  const g = gradeForAct(act);
  const t = Math.abs(g.temperature) / 0.08;
  const base = g.temperature >= 0 ? WARM_TINT : COOL_TINT;
  // The lift opens the shadows, which on a multiply chain means raising the
  // floor rather than adding light: a brightness just under 1 with the
  // contrast pulled in slightly.
  //
  // BRIGHTNESS_PULL is the grade's own darkening — the thing that stops a
  // bright blue-sky JPEG sitting several stops above the authored scenes it
  // cuts against. It used to live only on the CSS path, as a flat black layer
  // at 0.15, which is why the shader read a third brighter than CSS even once
  // the rest of the chain matched. It is part of the grade, so it belongs in
  // the operations both paths run.
  return {
    saturation: g.saturation,
    contrast: 1 + 0.04 - g.lift * 0.35,
    brightness: BRIGHTNESS_PULL * (1 - g.lift * 0.55),
    multiply: [
      1 + (base[0] - 1) * t,
      1 + (base[1] - 1) * t,
      1 + (base[2] - 1) * t,
    ],
  };
};

/** Stagger helper: nth element enters this many frames late. */
export const stagger = (n: number) => n * SYS.stagger;
