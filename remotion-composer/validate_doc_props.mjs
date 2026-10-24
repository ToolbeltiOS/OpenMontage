// Validate a scene plan's authored props against the composer's own Zod schemas.
//
// WHY THIS EXISTS
// ---------------
// lib/buildability.py checks that a component exists and that its REQUIRED
// props are present, which is what stops a described slot rendering as a text
// card. It cannot check types, because the types live here in TypeScript. And
// Zod objects strip unknown keys rather than rejecting them, so a prop with
// the wrong NAME does not fail — it vanishes, and the scene renders without
// the thing that prop was carrying. A rect given `width` instead of `w` draws
// a rectangle of no width: nothing on screen, no error anywhere.
//
// Measured on this film's first scene plan: a schematic using x1/y1 on a line,
// cx/cy on a circle, width/height on a rect, "accent" as an SVG colour, and a
// texture_field with a numeric seed and a density of 0.35 against a schema
// that wants a string and 4..400. Every one of those would have rendered as a
// silent blank and passed every Python gate in the pipeline.
//
//   node validate_doc_props.mjs <scene_plan.json>
//
// Run from the composer directory: the Zod import resolves from here.

import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const planPath = process.argv[2];
if (!planPath) {
  console.error("usage: node validate_doc_props.mjs <scene_plan.json>");
  process.exit(2);
}

// The schemas are TypeScript. Bundle them to ESM with the esbuild that is
// already a dependency, rather than adding a TS runtime to the project.
// Inside the composer directory, not a temp one: `remotion` is marked
// external, so the bundle has to sit somewhere node can resolve it from.
const out = join(HERE, ".docprops_schemas.mjs");
execFileSync(
  join(HERE, "node_modules", ".bin", "esbuild"),
  [
    join(HERE, "src", "schemas", "docComponents.ts"),
    "--bundle",
    "--format=esm",
    "--platform=node",
    "--external:remotion",
    "--external:react",
    `--outfile=${out}`,
  ],
  { cwd: HERE, stdio: ["ignore", "ignore", "inherit"] },
);

const { DOC_COMPONENT_SCHEMAS } = await import(out);

const plan = JSON.parse(readFileSync(planPath, "utf8"));
const slots = plan.metadata?.slots ?? plan;

let authored = 0;
let failed = 0;
const problems = [];

for (const slot of slots) {
  const name = slot.component;
  if (!name) continue;
  authored += 1;
  const schema = DOC_COMPONENT_SCHEMAS[name];
  if (!schema) {
    problems.push(`${slot.slot_id}: no schema for component ${name}`);
    failed += 1;
    continue;
  }
  const result = schema.safeParse(slot.props ?? {});
  if (!result.success) {
    failed += 1;
    for (const issue of result.error.issues) {
      const where = issue.path.length ? issue.path.join(".") : "(root)";
      problems.push(`${slot.slot_id} [${name}] ${where}: ${issue.message}`);
    }
    continue;
  }
  // A key Zod stripped is a key the component will never see. Report it: the
  // prop was written for a reason and it is now not going to do anything.
  const kept = new Set(Object.keys(result.data));
  const dropped = Object.keys(slot.props ?? {}).filter((k) => !kept.has(k));
  if (dropped.length) {
    failed += 1;
    problems.push(
      `${slot.slot_id} [${name}]: props the schema does not know, and so ` +
        `silently drops: ${dropped.join(", ")}`,
    );
  }
}

console.log(`authored slots: ${authored}, failing: ${failed}`);
for (const p of problems.slice(0, 60)) console.log("  -", p);
if (problems.length > 60) console.log(`  ... and ${problems.length - 60} more`);
console.log("DOC PROPS:", failed === 0 ? "PASS" : "FAIL");
process.exit(failed === 0 ? 0 : 1);
