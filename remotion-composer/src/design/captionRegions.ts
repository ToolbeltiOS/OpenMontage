/**
 * Which parts of the frame a scene has already spoken for.
 *
 * The burn-in caption layer is off by default — long-form ships a sidecar
 * track, because run #1 put text on screen for 99.4% of its runtime and paid
 * the bottom of every frame for it. When burn-in IS switched on (a short-form
 * cut-down, a silent-autoplay context), it has to find somewhere to sit that
 * the scene is not already using, and suppress itself entirely when the scene
 * is already carrying text.
 *
 * Regions are normalised 0..1 rects in frame space.
 */

export type Region = { x: number; y: number; w: number; h: number };

/** Where the persistent frame's own furniture lives. Never written over. */
export const CHROME_REGIONS: Region[] = [
  { x: 0, y: 0, w: 1, h: 0.1 },        // act strip + channel mark
  { x: 0, y: 0.9, w: 1, h: 0.1 },      // scene index, coords, source caption
];

/**
 * Scene types whose whole point is text on screen. While one of these is up,
 * the caption layer renders nothing: two blocks of text competing for one
 * frame is worse than a missing line, and the component's text is the one
 * carrying the meaning.
 */
export const TEXT_BEARING = new Set([
  "text_card",
  "stat_card",
  "callout",
  "comparison",
  "hero_title",
  "section_title",
  "act_title_card",
  "title_sequence",
  "evidence_card",
  "scale_comparison",
  "document_reveal",
  "timeline",
  "schematic",
  "outro_cta",
]);

/** The regions a given cut occupies, beyond the chrome every scene carries. */
export const occupiedRegions = (cut: {
  type?: string;
  annotations?: { x: number; y: number }[];
  measurement?: { from: { x: number; y: number }; to: { x: number; y: number } };
  caption?: string;
  title?: string;
}): Region[] => {
  const regions: Region[] = [...CHROME_REGIONS];

  // An annotated still writes labels over the picture; each one claims a band
  // around its anchor, because a caption under a leader line is unreadable.
  for (const a of cut.annotations ?? []) {
    regions.push({ x: Math.max(0, a.x - 0.22), y: Math.max(0, a.y - 0.06), w: 0.44, h: 0.12 });
  }
  if (cut.measurement) {
    const { from, to } = cut.measurement;
    regions.push({
      x: Math.min(from.x, to.x),
      y: Math.min(from.y, to.y) - 0.04,
      w: Math.abs(to.x - from.x),
      h: Math.abs(to.y - from.y) + 0.08,
    });
  }
  if (cut.title) regions.push({ x: 0, y: 0.08, w: 1, h: 0.14 });
  return regions;
};

const overlaps = (a: Region, b: Region) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/**
 * The band the captions should sit in, or null when they should not render.
 *
 * Candidates run bottom-up, because a documentary subtitle belongs in the
 * lower third and the alternatives are fallbacks rather than choices.
 */
export const captionBand = (
  cut: { type?: string } & Parameters<typeof occupiedRegions>[0],
  safeMarginPct = 8,
): Region | null => {
  if (cut.type && TEXT_BEARING.has(cut.type)) return null;

  const m = safeMarginPct / 100;
  const taken = occupiedRegions(cut);
  const candidates: Region[] = [
    { x: m, y: 0.72, w: 1 - 2 * m, h: 0.16 },   // lower third, preferred
    { x: m, y: 0.62, w: 1 - 2 * m, h: 0.16 },   // a little higher
    { x: m, y: 0.14, w: 1 - 2 * m, h: 0.16 },   // upper third, last resort
  ];
  for (const band of candidates) {
    if (!taken.some((t) => overlaps(band, t))) return band;
  }
  return null;
};
