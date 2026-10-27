import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { SYS } from "./system";
import { GLYPHS } from "./glyphIndex";

/**
 * The house library, as the components see it.
 *
 * WHY A TEXTURE IS NOT A `plate`
 * ------------------------------
 * `Plate` exists to put a photograph behind a card, so it blurs its image to
 * 26px and dims it to 42% — at which point paper is no longer paper, it is a
 * brown smear. A texture has to stay legible as a surface while still sitting
 * *under* everything, so it gets its own treatment: a gentle tint and a
 * contrast reduction, and no blur.
 *
 * It goes in the plate layer all the same, which is the part that matters.
 * The plate carries the sustaining move and the grain pass; everything above
 * it is locked. A texture that drifted with the type would be the defect the
 * layer split was built to remove.
 */

/** name -> published path. The 12 textures, by what a component asks for. */
export const TEXTURES = {
  "aged-paper-1": "library/textures/aged-paper-1.jpg",
  "aged-paper-2": "library/textures/aged-paper-2.jpg",
  "aged-paper-3": "library/textures/aged-paper-3.jpg",
  parchment: "library/textures/parchment.jpg",
  sandstone: "library/textures/sandstone.jpg",
  granite: "library/textures/granite.jpg",
  basalt: "library/textures/basalt.jpg",
  sand: "library/textures/sand.jpg",
  slate: "library/textures/slate.jpg",
  "rusted-iron": "library/textures/rusted-iron.jpg",
  linen: "library/textures/linen.jpg",
  vellum: "library/textures/vellum.jpg",
} as const;

export type TextureName = keyof typeof TEXTURES;

/**
 * How a texture is treated. Paper reads light and takes the film's ink;
 * stone stays dark and sits behind light type, like every other plate.
 */
export type TextureKind = "paper" | "stone";

const TREATMENT: Record<TextureKind, React.CSSProperties> = {
  // Paper is lifted and desaturated rather than left at its own contrast:
  // an ambientCG scan at full strength is a loud, busy surface, and a card
  // sitting on it has to stay the thing being read.
  paper: { filter: "saturate(0.55) brightness(1.06) contrast(0.82)" },
  // Stone is pushed down to roughly the plate brightness the film already
  // uses, so a schematic over it reads the same as a schematic over a
  // photograph.
  stone: { filter: "saturate(0.35) brightness(0.40) contrast(0.95)" },
};

/** The paper tone the chrome inverts against. Matches SYS.paperInk's ground. */
export const PAPER_GROUND = "#D9CFBC";

export const TexturePlate: React.FC<{
  name: TextureName;
  kind?: TextureKind;
  /** 0..1, how much of the texture shows over the ground beneath it */
  strength?: number;
}> = ({ name, kind = "paper", strength = 1 }) => (
  <AbsoluteFill
    style={{ backgroundColor: kind === "paper" ? PAPER_GROUND : SYS.bg }}
  >
    <Img
      src={staticFile(TEXTURES[name])}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        opacity: strength,
        ...TREATMENT[kind],
      }}
    />
  </AbsoluteFill>
);

/**
 * The published path of a glyph, by name.
 *
 * THROWS ON AN UNKNOWN NAME, deliberately. A helper that returned a path to
 * nothing would render an empty box, and an empty box in a timeline is
 * exactly the kind of defect that survives review — nothing is obviously
 * wrong, there is simply less than there should be. The index is generated
 * from the manifest by `scripts/fetch_library.py`, so a name either exists
 * or is a typo.
 */
export function glyph(name: string): string {
  const path = GLYPHS[name];
  if (!path) {
    throw new Error(
      `glyph("${name}") does not exist. ${Object.keys(GLYPHS).length} glyphs ` +
        `are available; see remotion-composer/src/design/glyphIndex.ts.`,
    );
  }
  return staticFile(path);
}

/**
 * A glyph, inked in the film's colour.
 *
 * The SVGs are served with `fill="currentColor"` — `scripts/fetch_library.py`
 * strips the opaque background tile game-icons ships and rewrites the fill,
 * because the originals are white-on-black and no CSS can recolour those.
 * Here that is spent: the mark takes `color`, like type does, and a glyph
 * beside a date reads as part of the same film.
 */
export const Glyph: React.FC<{
  name: string;
  size?: number;
  color?: string;
  opacity?: number;
  style?: React.CSSProperties;
}> = ({ name, size = 48, color = SYS.accent, opacity = 1, style }) => (
  <span
    aria-hidden
    style={{
      display: "inline-block",
      width: size,
      height: size,
      color,
      opacity,
      // The SVG is served as an image, so `color` cannot reach inside it.
      // A mask does: the glyph's own alpha cuts a hole in a block of colour,
      // which is why the background tile had to go.
      backgroundColor: "currentColor",
      WebkitMaskImage: `url(${glyph(name)})`,
      maskImage: `url(${glyph(name)})`,
      WebkitMaskSize: "contain",
      maskSize: "contain",
      WebkitMaskRepeat: "no-repeat",
      maskRepeat: "no-repeat",
      WebkitMaskPosition: "center",
      maskPosition: "center",
      ...style,
    }}
  />
);

/**
 * A glyph inside an SVG scene.
 *
 * `Glyph` is an HTML element and tints itself with a CSS mask, which is what
 * lets one `color` rule ink every mark in the film. An SVG `<image>` cannot
 * do that — it paints the file as-is and ignores `fill` — so the same span
 * is placed through a `foreignObject`. The Timeline draws in SVG at frame
 * scale, so `x`/`y` here are the frame's own pixels.
 *
 * `x`/`y` are the glyph's CENTRE, because every other mark in these scenes
 * is positioned by its centre and a glyph anchored by its corner sits half
 * a glyph off whatever it labels.
 */
export const SvgGlyph: React.FC<{
  name: string;
  x: number;
  y: number;
  size?: number;
  color?: string;
  opacity?: number;
}> = ({ name, x, y, size = 36, color = SYS.accent, opacity = 1 }) => (
  <foreignObject
    x={x - size / 2}
    y={y - size / 2}
    width={size}
    height={size}
    style={{ overflow: "visible" }}
  >
    <Glyph name={name} size={size} color={color} opacity={opacity} />
  </foreignObject>
);
