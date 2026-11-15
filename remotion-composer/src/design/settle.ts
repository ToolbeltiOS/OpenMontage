/**
 * An entrance that is over returns its target EXACTLY.
 *
 * WHY THIS EXISTS
 * ---------------
 * A Remotion spring converges on its target; it never arrives. `leftScale` on
 * a comparison card is 1 - 9.5e-7 two seconds in and 1 - 6.1e-9 three seconds
 * in, which is the right answer to every question except the one the type-lock
 * gate asks.
 *
 * Type is rasterised to whole pixels. A line whose laid-out position lands on
 * exactly N.5 is decided by the last bits of the transform above it, so a
 * residual of 1e-8 is not a small movement — it is a coin flip between two
 * rasterisations a whole pixel apart, on every frame, forever. Run #6's c141
 * failed type lock at 1.003px for exactly this: 'casualties', the bottom line
 * of the card and so the line furthest from the transform origin, alternated
 * between two glyph images 0.9969px apart (frames 32143, 32144 and 32152 of
 * the delivered film, by byte hash of its own box), while the other 22 words
 * on the card never moved at all.
 *
 * Shrinking the residual cannot fix it. A position sitting exactly on the
 * boundary flips on any residual whatsoever, and the ones that did not flip
 * were not better damped — they were further from a boundary. `TextCard` holds
 * still today for that reason and no other.
 *
 * So the entrance is given an end. Before `ENTRANCE_PINNED_AT` the authored
 * motion plays untouched; from that frame on every animated value IS its
 * target, the transform is exactly identity, and every later frame computes
 * the same floats and rasterises to the same bytes.
 *
 * The frame is 54 because type lock samples a cut at `DEFAULT_SETTLE_S` — two
 * seconds, frame 60 — and a second later, so the card must be at rest before
 * frame 60 or the gate reads the difference between a converging spring and a
 * pinned one. The step at frame 54 is the residual at that frame: 6e-3 on the
 * indicator's scale, which moves its own glyphs by under a pixel for one
 * frame, and 1.3e-6 on the left column, which moves 'casualties' by 4e-4 px.
 * Nothing downstream of frame 54 moves at all.
 */
export const ENTRANCE_PINNED_AT = 54;

export const pinned = (frame: number, value: number, target: number): number =>
  frame >= ENTRANCE_PINNED_AT ? target : value;
