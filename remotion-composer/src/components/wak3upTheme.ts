/**
 * Design tokens for the wak3up-documentary playbook.
 *
 * This file is now a thin adapter over `src/design/system.ts`, which is the
 * single source of truth for palette, type families and the motion language.
 * The five doc components were written against this shape, so it stays — but
 * nothing is defined twice, and `EASE` is the system's own entrance easing so
 * every component shares one easing family.
 */
import { SYS, EXPO_OUT } from "../design/system";

export const wak3up = {
  bg: SYS.bg,
  plate: SYS.plate,
  surface: SYS.surface,
  text: SYS.text,
  muted: SYS.muted,
  faint: SYS.faint,
  accent: SYS.accent,
  accentDim: SYS.accentDim,
  rule: SYS.rule,
  paper: SYS.paper,
  paperInk: SYS.paperInk,
  serif: SYS.display,
  sans: SYS.label,
  mono: SYS.data,
} as const;

/** Frames -> seconds helper used by every doc component. */
export const atSec = (seconds: number, fps: number) => Math.round(seconds * fps);

/**
 * The film's single entrance easing. expo-out: fast commit, long settle.
 * Re-exported from the design system so there is exactly one curve in the film.
 */
export const EASE = EXPO_OUT;
