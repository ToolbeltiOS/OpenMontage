/**
 * The consumer the scene schemas never had.
 *
 * Run by `lib/build_render_props.py` on the props it is about to write, so a
 * prop the composer cannot draw is answered in seconds rather than at the
 * frame the cut starts. Reads a render_props.json, prints ONE json object on
 * stdout, and leaves the verdict to the caller:
 *
 *   { checked, failures: [{where, id, type, field, rule}], unchecked: {type: n} }
 *
 * It exits 0 whether or not it found anything. A non-zero exit here means the
 * CHECK broke, which is a different thing from the props being bad, and the
 * caller must not read the two as the same.
 */
import { validateCutProps, DOC_CUT_SCHEMAS } from "./docComponents";
import * as fs from "fs";

const path = process.argv[2];
if (!path) {
  console.error("usage: validate_cut_props_cli <render_props.json>");
  process.exit(2);
}

let data: any;
try {
  data = JSON.parse(fs.readFileSync(path, "utf8"));
} catch (e) {
  console.error(`cannot read ${path}: ${(e as Error).message}`);
  process.exit(2);
}

const failures: {
  where: string; id: string; type: string; field: string; rule: string;
}[] = [];
const unchecked: Record<string, number> = {};
let checked = 0;

for (const [where, items] of [
  ["cut", data.cuts ?? []],
  ["overlay", data.overlays ?? []],
] as const) {
  if (!Array.isArray(items)) continue;
  for (const item of items as any[]) {
    const type = item?.type ?? item?.scene_type;
    if (!type) continue;
    const issues = validateCutProps(type, item);
    if (issues === null) {
      unchecked[type] = (unchecked[type] ?? 0) + 1;
      continue;
    }
    checked += 1;
    for (const i of issues) {
      failures.push({
        where,
        id: String(item?.id ?? "?"),
        type: String(type),
        field: i.field,
        rule: i.rule,
      });
    }
  }
}

process.stdout.write(
  JSON.stringify({
    checked,
    failures,
    unchecked,
    known: Object.keys(DOC_CUT_SCHEMAS).sort(),
  }),
);
