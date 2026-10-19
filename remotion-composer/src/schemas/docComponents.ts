import { z } from "zod";

/**
 * Props schemas for the eight documentary components.
 *
 * These exist so the scene-plan BUILDABILITY CHECK can fail a slot before a
 * render is attempted. Run #1 stalled at compose because 79 slots named
 * graphics that had no component behind them — descriptions, not scenes.
 *
 * Every scene type accepts the same persistent-frame props (`CHROME`), which
 * is what makes the dossier furniture identical across a cut.
 */

const sec = z.number().min(0).describe("seconds from scene start");
const unit = z.number().min(0).max(1).describe("0..1 fraction of the frame");

/**
 * The persistent frame layer. Optional everywhere — a scene without an act
 * number simply renders without that strip — but the names are fixed so a
 * slot cannot invent its own.
 */
const CHROME = {
  actNumber: z.string().optional(),
  actTitle: z.string().optional(),
  sceneIndex: z.string().optional(),
  coords: z.string().optional(),
  kicker: z.string().optional(),
  source: z.string().optional(),
};

export const AnnotatedStillSchema = z.object({
  image: z.string().min(1),
  parallax: z.boolean().optional(),
  parallaxFrom: z.number().positive().optional(),
  parallaxTo: z.number().positive().optional(),
  annotations: z
    .array(
      z.object({
        label: z.string().min(1),
        x: unit,
        y: unit,
        leader: z.boolean().optional(),
        reveal_at: sec,
        side: z.enum(["left", "right"]).optional(),
      }),
    )
    .optional(),
  measurement: z
    .object({
      text: z.string().min(1),
      from: z.object({ x: unit, y: unit }),
      to: z.object({ x: unit, y: unit }),
      reveal_at: sec,
    })
    .optional(),
  cutaway: z
    .object({ x: unit, y: unit, w: unit, h: unit, reveal_at: sec, label: z.string().optional() })
    .optional(),
  caption: z.string().optional(),
  title: z.string().optional(),
  dim: z.number().min(0).max(1).optional(),
  ...CHROME,
});

export const SchematicSchema = z.object({
  viewBox: z.string().optional(),
  layers: z
    .array(
      z.object({
        id: z.string().min(1),
        kind: z.enum(["path", "rect", "circle", "line", "text", "polyline"]),
        d: z.string().optional(),
        x: z.number().optional(),
        y: z.number().optional(),
        x2: z.number().optional(),
        y2: z.number().optional(),
        w: z.number().optional(),
        h: z.number().optional(),
        r: z.number().optional(),
        points: z.string().optional(),
        text: z.string().optional(),
        stroke: z.string().optional(),
        fill: z.string().optional(),
        strokeWidth: z.number().optional(),
        fontSize: z.number().optional(),
        dashed: z.boolean().optional(),
        anchor: z.enum(["start", "middle", "end"]).optional(),
      }),
    )
    .min(1),
  reveals: z
    .array(
      z.object({
        layer_id: z.string().min(1),
        at: sec,
        effect: z.enum(["draw", "fade", "slide-in"]),
        duration: z.number().positive().optional(),
      }),
    )
    .optional(),
  labels: z
    .array(
      z.object({
        text: z.string().min(1),
        x: z.number(),
        y: z.number(),
        at: sec,
        anchor: z.enum(["start", "middle", "end"]).optional(),
        accent: z.boolean().optional(),
        level: z.enum(["label", "data"]).optional(),
      }),
    )
    .optional(),
  title: z.string().optional(),
  caption: z.string().optional(),
  ...CHROME,
});

export const MapRouteSchema = z.object({
  route: z.array(z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90)])).min(2),
  markers: z
    .array(
      z.object({
        lon: z.number().min(-180).max(180),
        lat: z.number().min(-90).max(90),
        label: z.string().min(1),
        at: sec,
        dx: z.number().optional(),
        dy: z.number().optional(),
      }),
    )
    .optional(),
  center: z.tuple([z.number(), z.number()]).optional(),
  scale: z.number().positive().optional(),
  draw_seconds: z.number().positive().optional(),
  draw_at: sec.optional(),
  distance_callout: z.object({ text: z.string().min(1), at: sec }).optional(),
  title: z.string().optional(),
  caption: z.string().optional(),
  arc: z.boolean().optional(),
  ...CHROME,
});

export const TimelineSchema = z.object({
  events: z
    .array(
      z.object({
        year: z.number().int().describe("negative = BC"),
        label: z.string().min(1),
        text: z.string().optional(),
        at: sec,
        accent: z.boolean().optional(),
      }),
    )
    .min(1),
  orientation: z.enum(["horizontal", "vertical"]).optional(),
  span: z.tuple([z.number().int(), z.number().int()]).optional(),
  playhead: z.boolean().optional(),
  title: z.string().optional(),
  caption: z.string().optional(),
  ...CHROME,
});

export const DocumentRevealSchema = z.object({
  // CHROME first: this scene's own `source` is the document's citation, which
  // is what renders under the quote. It deliberately shadows the chrome field.
  ...CHROME,
  headline: z.string().optional(),
  lines: z.array(z.object({ text: z.string().min(1), at: sec, emphasis: z.boolean().optional() })).min(1),
  source: z.string().optional(),
  image: z.string().optional(),
  paper: z.enum(["light", "dark"]).optional(),
  light_sweep: z.boolean().optional(),
  sweep_at: sec.optional(),
  caption: z.string().optional(),
});

/* ───────────────────── design-pass scene types ─────────────────────────── */

export const ActTitleCardSchema = z.object({
  act: z.string().min(1).describe('as written, e.g. "ACT II"'),
  title: z.string().min(1),
  epigraph: z.string().optional().describe("one line, from the act's own narration"),
  image: z.string().optional(),
  fade_in: z.number().min(0).optional(),
  fade_out: z.number().min(0).optional(),
});

export const EvidenceCardSchema = z.object({
  index: z.string().optional().describe("ledger id, e.g. c38"),
  claim: z.string().min(1),
  attribution: z.string().min(1).describe("author, journal, year — as the ledger records it"),
  detail: z.string().optional(),
  status: z
    .enum(["peer_reviewed", "contested", "unpublished", "measured", "claim"])
    .optional()
    .describe("the honesty chip; a contested claim must not render as settled"),
  caption: z.string().optional(),
  ...CHROME,
});

export const ScaleComparisonSchema = z.object({
  items: z
    .array(
      z.object({
        label: z.string().min(1),
        value: z.number(),
        note: z.string().optional(),
        hero: z.boolean().optional(),
      }),
    )
    .min(2)
    .describe("at least two — a single bar compares nothing"),
  unit: z.string().min(1),
  decimals: z.number().int().min(0).max(3).optional(),
  title: z.string().optional(),
  footnote: z.string().optional().describe("the spread or the disagreement, stated on screen"),
  caption: z.string().optional(),
  at: sec.optional(),
  ...CHROME,
});

export const OutroCtaSchema = z.object({
  title: z.string().min(1),
  kicker: z.string().optional(),
  like_at: sec.describe("seconds from scene start when the narration says 'like'"),
  subscribe_at: sec.describe("seconds from scene start when it says 'subscribe'"),
  subscribe_label: z.string().optional(),
  sceneIndex: z.string().optional(),
  actNumber: z.string().optional(),
  actTitle: z.string().optional(),
});

export const DOC_COMPONENT_SCHEMAS = {
  annotated_still: AnnotatedStillSchema,
  schematic: SchematicSchema,
  map_route: MapRouteSchema,
  timeline: TimelineSchema,
  document_reveal: DocumentRevealSchema,
  act_title_card: ActTitleCardSchema,
  evidence_card: EvidenceCardSchema,
  scale_comparison: ScaleComparisonSchema,
  outro_cta: OutroCtaSchema,
} as const;

export type DocComponentName = keyof typeof DOC_COMPONENT_SCHEMAS;

export const DOC_COMPONENT_NAMES = Object.keys(DOC_COMPONENT_SCHEMAS) as DocComponentName[];

/** Validate one slot's props. Returns null on success, else a readable reason. */
export function validateDocProps(name: string, props: unknown): string | null {
  const schema = (DOC_COMPONENT_SCHEMAS as Record<string, z.ZodTypeAny>)[name];
  if (!schema) return `unknown component "${name}" (known: ${DOC_COMPONENT_NAMES.join(", ")})`;
  const r = schema.safeParse(props);
  if (r.success) return null;
  return r.error.issues.map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`).join("; ");
}
