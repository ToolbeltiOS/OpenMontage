/**
 * Where a point of the photograph has got to, in a 2.5D render.
 *
 * WHY THIS IS A LOOKUP AND NOT A FORMULA
 * --------------------------------------
 * The 2D treatment moves a plate with `scale(S) translateX(D%)`, and
 * `AnnotatedStill` inverts that in closed form to put an annotation's dot
 * back on its feature. Three lines of arithmetic, exact.
 *
 * A 2.5D render has no such inverse. DepthFlow's shader RAYMARCHES a
 * displaced surface: each output pixel walks along a ray until it hits the
 * height field, so where a given point of the photograph lands depends on
 * the depth map along the whole path. There is no expression for it.
 *
 * So it is MEASURED, once, at build time, by `scripts/anchor_track.py` —
 * which renders luma ramps through the same shader with the same state and
 * reads the mapping back out — and the result travels with the cut as a
 * table of positions per frame. This module is the read side.
 *
 * The cost of the measurement is the thing that makes it trustworthy: the
 * track cannot disagree with the render, because it was taken FROM the
 * render. A formula can, and the formula that went wrong looked right.
 */

export interface AnchorTrack {
  /** Render size the track was measured at. */
  width: number;
  height: number;
  /** How many samples each anchor has. */
  frames: number;
  /** keyed by `anchorKey(x, y)`, each a list of [u, v] in 0..1 */
  anchors: Record<string, [number, number][]>;
}

/**
 * The key an anchor is stored under. FOUR DECIMALS, and the writer and the
 * reader have to agree exactly or every lookup misses and every annotation
 * silently falls back to the flat inverse — which is the failure this whole
 * branch exists to remove. `scripts/anchor_track.py` formats with `:.4f`.
 */
export const anchorKey = (x: number, y: number): string =>
  `${x.toFixed(4)},${y.toFixed(4)}`;

/**
 * The anchor's position in SCREEN PIXELS at this frame, or null if this
 * anchor was never tracked.
 *
 * Null is deliberate and must stay. A missing track is not "no movement" —
 * it means the build stage did not measure this anchor, and the caller has
 * to either fall back visibly or fail. Returning the untracked position
 * would put the dot somewhere plausible and wrong, which is exactly how the
 * flat renders got through review.
 */
export function trackedPoint(
  track: AnchorTrack | undefined,
  x: number,
  y: number,
  frame: number,
  durationInFrames: number,
  width: number,
  height: number,
): [number, number] | null {
  if (!track) return null;
  const pts = track.anchors[anchorKey(x, y)];
  if (!pts || pts.length === 0) return null;
  if (pts.length === 1) return [pts[0][0] * width, pts[0][1] * height];

  /*
   * The track is sampled over the clip, the scene is cut to its own length,
   * and the two are not the same number of frames. Map by PROPORTION rather
   * than by index: a track of 240 samples read at index `frame` would run
   * out a third of the way through a 360-frame hold and then clamp, which
   * reads as the annotation sticking while the picture carries on.
   */
  const span = Math.max(durationInFrames - 1, 1);
  const t = Math.min(Math.max(frame / span, 0), 1) * (pts.length - 1);
  const i = Math.floor(t);
  const j = Math.min(i + 1, pts.length - 1);
  const f = t - i;

  // Interpolated, because a 30 fps track under a 30 fps scene still lands
  // between samples once the proportion above is applied, and stepping
  // between samples makes a dot that should glide tick instead.
  const u = pts[i][0] + (pts[j][0] - pts[i][0]) * f;
  const v = pts[i][1] + (pts[j][1] - pts[i][1]) * f;
  return [u * width, v * height];
}
