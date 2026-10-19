/**
 * Font loading for the documentary design system.
 *
 * Four type levels, three families. Loaded once, at module scope, so every
 * composition that imports anything from `src/design` gets them. Weights are
 * restricted to the ones the TYPE ramp actually uses — a smaller download and
 * no accidental drift into a weight the system does not define.
 */
import { loadFont as loadDisplay } from "@remotion/google-fonts/SourceSerif4";
import { loadFont as loadSans } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const displayFont = loadDisplay("normal", {
  weights: ["400", "600"],
  subsets: ["latin", "latin-ext"],
});

export const sansFont = loadSans("normal", {
  weights: ["400", "500"],
  subsets: ["latin", "latin-ext"],
});

export const monoFont = loadMono("normal", {
  weights: ["400", "500"],
  subsets: ["latin", "latin-ext"],
});

/** Resolved family names, used by `system.ts` so the tokens stay the single source. */
export const FAMILIES = {
  display: `${displayFont.fontFamily}, Georgia, serif`,
  sans: `${sansFont.fontFamily}, system-ui, sans-serif`,
  mono: `${monoFont.fontFamily}, ui-monospace, monospace`,
} as const;

/** Await before rendering a still so text never measures against a fallback. */
export const fontsReady = () =>
  Promise.all([displayFont.waitUntilDone(), sansFont.waitUntilDone(), monoFont.waitUntilDone()]);
