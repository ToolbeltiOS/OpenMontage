/**
 * Where a map's marker labels go when two of them want the same place.
 *
 * WHAT THIS IS FOR
 * ----------------
 * `MapRoute` drew every label at its marker plus a fixed offset and never
 * asked whether two of them overlapped. On film #6 (published 2026-11-23)
 * two did, in both of the cuts that carry more than one marker:
 *
 *   c006  "RELEASED FROM FLEET SUBMARINES" over "HARBOUR ENTRANCE"
 *   c112  "NIIHAU — A ZERO CAME DOWN HERE" over "OAHU"
 *
 * The delivered frames read "NIIHAU_OAHU" and a pile of overlapping
 * capitals. The maps being far too wide made it worse — every marker
 * collapsed towards the centre of the frame — but the collision is its own
 * fault and survives a correctly framed map whenever two places are close
 * together, which on a map of a route they usually are.
 *
 * THE RULE: a label whose box intersects one already placed is pushed
 * ALONG ITS OWN LEADER — the direction from its marker to where the label
 * sits — until it is clear. Along the leader and not sideways, because the
 * leader is what tells a reader which mark the label belongs to; moving it
 * perpendicular breaks that line of sight, and moving it to the other side
 * of the mark can put it over the route.
 *
 * DETERMINISTIC, AND NOT A FUNCTION OF TIME. Placement is computed over
 * EVERY marker of the cut, not just the ones that have appeared yet. A
 * label that shifted when a later marker faded in would be type that moves
 * on screen, which is the defect `lib/verify_type_lock.py` exists to fail
 * a film for.
 *
 * React-free so the rule can be exercised directly —
 * `tests/composer/test_map_label_collision.py` bundles it with the
 * composer's own esbuild and runs it under node, against film #6's real
 * label sets.
 */

export interface LabelAnchor {
  /** where the marker is, in screen px */
  x: number;
  y: number;
  label: string;
  /** the authored offset, which is the leader's direction and length */
  dx?: number;
  dy?: number;
}

export interface LabelBox {
  x: number;
  y: number;
  w: number;
  h: number;
  dx: number;
  dy: number;
  /** how many steps it had to be pushed; 0 means it sat where it asked */
  pushed: number;
}

/** `MapRoute`'s own defaults for a label with no authored offset. */
export const DEFAULT_DX = 24;
export const DEFAULT_DY = 7;

/**
 * Width of one character as a fraction of the font size, for uppercase
 * Inter at this tracking. The same approximation `Timeline` uses to lay
 * out its year labels; a real measurement needs a DOM and this runs in
 * the same frame budget as everything else.
 */
export const CHAR_W = 0.72;

/** Space left between two boxes that are not allowed to touch. */
export const PAD = 6;

/** How far one push moves a label, as a fraction of its height. */
export const STEP = 1.1;

/** Past this many pushes the map is too crowded for this rule to fix. */
export const MAX_PUSHES = 14;

export const boxOf = (
  a: LabelAnchor, dx: number, dy: number, fontSize: number,
): Omit<LabelBox, "dx" | "dy" | "pushed"> => {
  const w = Math.max(1, a.label.length) * fontSize * CHAR_W;
  const h = fontSize * 1.25;
  // `dy` is a baseline offset in the SVG, so the box sits above it.
  return { x: a.x + dx, y: a.y + dy - h * 0.78, w, h };
};

const hits = (a: { x: number; y: number; w: number; h: number },
              b: { x: number; y: number; w: number; h: number }): boolean =>
  a.x < b.x + b.w + PAD && a.x + a.w + PAD > b.x &&
  a.y < b.y + b.h + PAD && a.y + a.h + PAD > b.y;

/**
 * Offsets for every label, in the order given. The first marker keeps the
 * place it asked for; each one after it is pushed along its own leader
 * until it clears everything already placed.
 */
export const placeLabels = (
  anchors: LabelAnchor[], fontSize: number,
): LabelBox[] => {
  const placed: LabelBox[] = [];
  for (const a of anchors) {
    const dx0 = a.dx ?? DEFAULT_DX;
    const dy0 = a.dy ?? DEFAULT_DY;
    // The leader's direction, from the offset the edit authored. A label
    // with NO offset at all still has one — MapRoute's default puts it to
    // the right — but a label authored straight up has dx 0 on purpose,
    // and treating that 0 as "no direction" pushed it sideways out of its
    // own leader. Only an offset of nothing at all takes the default.
    const flat = dx0 === 0 && dy0 === 0;
    const lx = flat ? DEFAULT_DX : dx0;
    const ly = flat ? DEFAULT_DY : dy0;
    const len = Math.hypot(lx, ly) || 1;
    const ux = lx / len;
    const uy = ly / len;
    const step = fontSize * 1.25 * STEP;

    let pushed = 0;
    let dx = dx0;
    let dy = dy0;
    let box = boxOf(a, dx, dy, fontSize);
    while (pushed < MAX_PUSHES && placed.some((p) => hits(box, p))) {
      pushed += 1;
      dx = dx0 + ux * step * pushed;
      dy = dy0 + uy * step * pushed;
      box = boxOf(a, dx, dy, fontSize);
    }
    placed.push({ ...box, dx, dy, pushed });
  }
  return placed;
};
