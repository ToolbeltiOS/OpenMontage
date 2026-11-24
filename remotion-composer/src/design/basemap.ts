/**
 * The ceiling on a terrain basemap's drift, in one place.
 *
 * WHY A SHARED CONSTANT AND NOT A NUMBER IN EACH FILE
 * ---------------------------------------------------
 * `basemap_drift` is read by `TerrainBase` as
 *
 *     scale(1 + drift)   translateX(-drift * 40 * progress)%
 *
 * so it is not a taste setting with a wide safe range: it is a transform
 * multiplier. Six cuts in the Pearl Harbor film authored 1.1 to 1.5, which
 * is a map zoomed to 2.3x and slid 52% out of the frame — and none of them
 * ever drew, because `Explainer` dropped the prop on the floor before the
 * component could be harmed by it. When the prop was wired through
 * (2026-11-24) the value became live for the first time, so the ceiling the
 * schema had always declared had to become a thing the component enforces
 * too.
 *
 * The zod schema (`schemas/docComponents.ts`) and `MapRoute` therefore read
 * the same constant from here. A second copy of a ceiling is how `note`
 * survived in `callout_type` and how the drift sat 16x over the limit for
 * six films: the rule existed twice and only one copy was checked.
 *
 * 0.08 is the schema's long-standing value — about five times the 1-2% the
 * component documents as its working range, which leaves room for a
 * deliberately livelier shot without letting the map leave the frame.
 */
export const MAX_BASEMAP_DRIFT = 0.08;

/** The drift a map takes when the edit does not ask for one. */
export const DEFAULT_BASEMAP_DRIFT = 0.015;

/**
 * The drift a shot will actually be given: the authored value, held inside
 * the ceiling. Out-of-range values are clamped rather than ignored, because
 * a map that drifts slightly less than asked is a map; one that drifts 1.3
 * is a blank frame with a route somewhere off the edge of it.
 */
export const clampBasemapDrift = (drift?: number): number => {
  if (typeof drift !== "number" || Number.isNaN(drift)) {
    return DEFAULT_BASEMAP_DRIFT;
  }
  return Math.min(Math.max(drift, 0), MAX_BASEMAP_DRIFT);
};
