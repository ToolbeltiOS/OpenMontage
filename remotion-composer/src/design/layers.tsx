import React from "react";

/**
 * Splitting the film into a PLATE layer and a TYPE layer.
 *
 * WHY
 * ---
 * Two things made the type in authored scenes shake.
 *
 * The first is that the sustaining move — added so that an authored graphic
 * held for fifteen seconds is not a frozen frame — moved the type with it, by
 * fractions of a pixel per frame. Fractional movement of a glyph is not
 * movement; it is the rasteriser redistributing the same stems across
 * different subpixels every frame, which reads as a shimmer along every edge.
 *
 * The second is the film look. It runs as a pass over the finished frame, so
 * its grain and its chromatic offset land ON the glyph edges — per-frame noise
 * exactly where the eye is most sensitive to it. Both faults are invisible in
 * a still and unmistakable in motion.
 *
 * The fix for the second one is a composite order, and a composite order
 * cannot exist while the film is one flat render. So the film is rendered
 * twice from the same code: once with the type hidden, which is what the
 * shader runs over, and once with ONLY the type, over transparency, which is
 * laid on top afterwards. Plate, then grade and vignette and grain, then type.
 *
 * HOW
 * ---
 * Not by moving components around — by hiding them, so that both renders come
 * from the same tree and cannot drift apart. Every text element in the system
 * carries `om-type`; `visibility` is inherited but can be turned back on
 * further down, so one rule hides the world and a second brings the type back.
 *
 * Hiding rather than unmounting matters: in the plate render the type still
 * takes up its space, so anything laid out around it — a card sized to its
 * content, a rule drawn under a title — is in exactly the place it will be in
 * the finished frame.
 *
 * The one thing this cannot do is composite a glyph's own vignette. Type keeps
 * the vignette because the vignette is lighting and the type is in the scene;
 * it is applied to the plate under it, which is where the eye reads it from.
 */
export type LayerMode = "all" | "plate" | "type";

/** The class every text element in the film carries. */
export const TYPE_CLASS = "om-type";

const LayerModeContext = React.createContext<LayerMode>("all");

export const useLayerMode = () => React.useContext(LayerModeContext);

/**
 * True when type should be laid out but not inked — the plate pass. Components
 * that draw their own text directly (SVG `<text>`, mostly) can ask, but they
 * are better off carrying TYPE_CLASS and letting the stylesheet do it.
 */
export const useTypeHidden = () => useLayerMode() === "plate";

const CSS: Record<LayerMode, string> = {
  all: "",
  // Lay the type out, ink nothing. Descendants inherit the hiding.
  plate: `.om-layer-plate .${TYPE_CLASS} { visibility: hidden; }`,
  // Hide the world, then bring the type back. `visibility` is the only
  // property that allows that: a hidden ancestor does not stop a visible
  // descendant from painting, which `display: none` and `opacity` both do.
  type:
    `.om-layer-type, .om-layer-type * { visibility: hidden; }\n` +
    `.om-layer-type .${TYPE_CLASS}, .om-layer-type .${TYPE_CLASS} * { visibility: visible; }`,
};

/**
 * Wraps the film in one of the two passes. `all` is the single flat render,
 * which is what Studio and every short-form composition still use.
 */
export const LayerScope: React.FC<{
  mode?: LayerMode;
  children: React.ReactNode;
}> = ({ mode = "all", children }) => {
  if (mode === "all") {
    return <>{children}</>;
  }
  return (
    <LayerModeContext.Provider value={mode}>
      <style>{CSS[mode]}</style>
      <div
        className={`om-layer-${mode}`}
        style={{
          position: "absolute",
          inset: 0,
          // The type pass is laid over the graded plate, so it must carry
          // nothing of its own behind the glyphs.
          backgroundColor: mode === "type" ? "transparent" : undefined,
        }}
      >
        {children}
      </div>
    </LayerModeContext.Provider>
  );
};

/**
 * Marks a subtree as type. Use it for text a component draws itself rather
 * than through `<T>` — an SVG label, a date on an axis.
 */
export const typeClass = (existing?: string) =>
  existing ? `${existing} ${TYPE_CLASS}` : TYPE_CLASS;
