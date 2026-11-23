import { z } from "zod";
// The end card ships its own schema with the component, so there is one
// definition rather than a copy that can drift from it.
import { outroCtaSchema } from "../components/OutroCta";

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

/** The terrain tile under a map, cut by scripts/build_basemap_tile.py. */
export const TerrainTileSchema = z.object({
  src: z.string().min(1),
  bounds: z.tuple([z.number(), z.number(), z.number(), z.number()])
    .describe("[west, south, east, north] of the tile, in degrees"),
});

export const GlobeDescentSchema = z.object({
  lon: z.number().min(-180).max(180),
  lat: z.number().min(-90).max(90),
  seconds: z.number().min(1).max(8).optional(),
  handoff_seconds: z.number().min(0).max(3).optional(),
  texture: z.string().optional(),
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
  basemap: TerrainTileSchema.optional(),
  basemap_drift: z.number().min(0).max(0.08).optional(),
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


/**
 * The film's own title card, placed after the cold open. Distinct from
 * act_title_card: that one is a chapter break inside a running film.
 */
export const TitleSequenceSchema = z.object({
  title: z.string().min(1),
  channel: z.string().optional(),
  kicker: z.string().optional().describe("the register, one line — not a summary"),
  image: z.string().optional(),
  sting_at: sec.optional().describe("the audio stage puts the sting on this same second"),
  fade_in: z.number().min(0).optional(),
  fade_out: z.number().min(0).optional(),
});

/**
 * Two framings of ONE subject, divided. Same place, same angle — two plates of
 * different subjects read as a cut, not as a comparison.
 */
export const BeforeAfterSchema = z.object({
  before: z.string().min(1),
  after: z.string().min(1),
  before_label: z.string().optional(),
  after_label: z.string().optional(),
  mode: z.enum(["wipe", "split"]).optional(),
  at: sec.optional().describe("when the divider starts moving (wipe)"),
  wipe_seconds: z.number().positive().optional(),
  rest: unit.optional().describe("where the divider rests, 0..1 from the left"),
  title: z.string().optional(),
  caption: z.string().optional(),
  ...CHROME,
});

/**
 * A full-frame figure and its subtitle.
 *
 * Added 2026-11-22: `stat_card` and `callout` were the two scene types in
 * the Pearl Harbor film with NO schema at all, so neither could be checked
 * even once the schemas had a consumer.
 */
export const StatCardSchema = z.object({
  stat: z.string().min(1),
  subtitle: z.string().optional(),
  statFontSize: z.number().positive().optional(),
  subtitleFontSize: z.number().positive().optional(),
  sustain: z.boolean().optional(),
  ...CHROME,
});

/**
 * A boxed aside.
 *
 * `callout_type` IS DELIBERATELY ABSENT. Which styles exist is read out of
 * `CalloutBox.tsx` by `check_callout_types`, and restating that list here
 * would be a second source of truth — which is the precise shape of the bug
 * that killed the 2026-11-21 render at frame 16301.
 */
export const CalloutSchema = z.object({
  text: z.string().min(1),
  title: z.string().optional(),
  backgroundColor: z.string().optional(),
  ...CHROME,
});

export const DOC_COMPONENT_SCHEMAS = {
  annotated_still: AnnotatedStillSchema,
  schematic: SchematicSchema,
  map_route: MapRouteSchema,
  globe_descent: GlobeDescentSchema,
  timeline: TimelineSchema,
  document_reveal: DocumentRevealSchema,
  act_title_card: ActTitleCardSchema,
  title_sequence: TitleSequenceSchema,
  before_after: BeforeAfterSchema,
  evidence_card: EvidenceCardSchema,
  scale_comparison: ScaleComparisonSchema,
  texture_field: z.object({
    kind: z.enum(["dust", "strata", "grain_drift", "depth_field", "scanline"]),
    seed: z.string().min(1).describe("what makes two instances different configurations"),
    density: z.number().min(4).max(400).optional(),
    angle: z.number().optional(),
    speed: z.number().min(0).max(4).optional(),
    ...CHROME,
  }),
  outro_cta: outroCtaSchema,
  stat_card: StatCardSchema,
  callout: CalloutSchema,
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

export { outroCtaSchema };

/* ─────────────────── what a CUT may carry, vs what a COMPONENT gets ────── */

/**
 * The schemas above describe what a COMPONENT receives. A CUT is not that:
 * `Explainer` maps one onto the other, supplying some props itself and
 * dropping others. Validating a cut against a component schema therefore
 * reports failures that are not defects — on 2026-11-22 the Pearl Harbor
 * film scored 85 of them while rendering perfectly well, because
 * `AnnotatedStill` is handed `image={cut.backgroundImage ?? cut.image}` and
 * no cut carries `image` at all.
 *
 * That gap is why these schemas sat for months with NO CONSUMER: pointed at
 * cuts they cried wolf, so nobody could turn them on. This registry closes
 * it. Every divergence from the component schema is declared HERE, with the
 * call site that justifies it, so "the cut contract" has one answer and the
 * difference between the two contracts is visible rather than assumed.
 *
 * A type with no entry of its own uses the component schema unchanged.
 */
export const DOC_CUT_SCHEMAS = {
  ...DOC_COMPONENT_SCHEMAS,

  /**
   * `Explainer` resolves the plate itself — `const plate = cut.backgroundImage
   * ?? cut.image` — and renders this scene type only when one of them is
   * truthy. So the cut owes a plate under either name, not `image`.
   */
  annotated_still: AnnotatedStillSchema.omit({ image: true })
    .extend({
      backgroundImage: z.string().min(1).optional(),
      image: z.string().min(1).optional(),
    })
    .refine((c) => Boolean(c.backgroundImage || c.image), {
      message:
        "needs backgroundImage or image — Explainer draws this cut only " +
        "when one of them resolves to a plate, and silently draws nothing " +
        "when neither does",
      path: ["backgroundImage"],
    }),

  /**
   * `seed` is interpolated into a string (`${seed}-x-${i}`), so a number is
   * as good as a string here and four cuts in the Pearl Harbor film author
   * one. `density` stays STRICT on purpose: it is used as
   * `Math.round(density)` for the element count, so the 0.4 those same cuts
   * carry rounds to zero and the texture beat draws nothing at all.
   */
  texture_field: DOC_COMPONENT_SCHEMAS.texture_field.extend({
    seed: z.union([z.string().min(1), z.number()]),
  }),

  /**
   * `map_route` deliberately has NO divergence. `basemap` and `basemap_drift`
   * are authored by the edit stage and are NOT passed on by `Explainer`, so
   * six cuts in the Pearl Harbor film ask for terrain and get none. Relaxing
   * the rule here would bless that; the fix is to wire the props through and
   * clamp the drift, which is owed separately.
   */
} as const;

export type DocCutName = keyof typeof DOC_CUT_SCHEMAS;

/** Validate one cut's props. Returns [] on success, else one reason per rule. */
export function validateCutProps(
  type: string,
  cut: unknown,
): { field: string; rule: string }[] | null {
  const schema = (DOC_CUT_SCHEMAS as Record<string, z.ZodTypeAny>)[type];
  if (!schema) return null; // no schema for this scene type — not checkable
  const r = schema.safeParse(cut);
  if (r.success) return [];
  return r.error.issues.map((i) => ({
    field: i.path.join(".") || "(root)",
    rule: i.message,
  }));
}
