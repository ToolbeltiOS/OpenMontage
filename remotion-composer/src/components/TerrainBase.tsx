import React, { useMemo } from "react";
import { AbsoluteFill, continueRender, delayRender, staticFile } from "remotion";
import { geoPath } from "d3-geo";
import { SYS, GRADE } from "../design/system";

export type TerrainTile = {
  /** path under public/, e.g. "basemaps/orcadian.jpg" */
  src: string;
  /** [west, south, east, north] of the tile, in degrees */
  bounds: [number, number, number, number];
};

/**
 * Natural Earth II with shaded relief, warped into the shot's projection.
 *
 * WHY THE WARP IS ONE PASS AND NOT A PROJECTION LOOP
 * --------------------------------------------------
 * The tile is cut in equirectangular, where the source lives
 * (scripts/build_basemap_tile.py). Mercator's x is linear in longitude and
 * its y depends on latitude alone, so the warp between the two is a vertical
 * stretch that varies by row and a uniform horizontal scale. One drawImage
 * per destination row does it exactly — about a thousand calls, once per
 * scene — where a per-pixel inverse projection would be two million.
 *
 * It runs inside delayRender so the frame is not captured before the tile has
 * decoded. A map that screenshots mid-decode renders a route over nothing,
 * which is how the before/after plates failed the first time.
 *
 * TREATMENT
 * ---------
 * Land keeps its relief and is desaturated and lifted into the film's grade.
 * Ocean is flooded with the palette rather than left Natural Earth's blue:
 * the mask is the same coastline geometry the map already draws, so the tint
 * lands exactly on the coast instead of being colour-keyed out of the raster.
 */
export const TerrainBase: React.FC<{
  tile: TerrainTile;
  /** the shot's projection, already centred and scaled */
  projection: any;
  /** land geometry, used as the ocean mask */
  land: any;
  width: number;
  height: number;
  /** 0..1 of the shot elapsed, for the drift */
  progress: number;
  /** total drift across the shot, as a fraction of the frame. 1-2% */
  drift?: number;
}> = ({ tile, projection, land, width, height, progress, drift = 0.015 }) => {
  const [handle] = React.useState(() => delayRender("terrain basemap"));
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const [ready, setReady] = React.useState(false);

  const landPath = useMemo(() => {
    const gp = geoPath(projection as never) as never as (g: unknown) => string;
    return gp(land);
  }, [projection, land]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      const [west, south, east, north] = tile.bounds;
      const degPerPx = (east - west) / img.width;

      // Where the tile's own corners land in the shot's projection. Rows are
      // walked in destination space and pulled from the source, so nothing is
      // left unpainted by rounding.
      ctx.clearRect(0, 0, width, height);
      const [xW] = projection([west, (south + north) / 2]) as [number, number];
      const [xE] = projection([east, (south + north) / 2]) as [number, number];
      const destW = xE - xW;

      for (let y = 0; y < height; y += 1) {
        const inv = projection.invert?.([width / 2, y + 0.5]);
        if (!inv) continue;
        const lat = inv[1];
        if (lat > north || lat < south) continue;
        const srcY = (north - lat) / degPerPx;
        ctx.drawImage(img, 0, Math.min(img.height - 1, Math.max(0, srcY)),
                      img.width, 1, xW, y, destW, 1);
      }
      setReady(true);
      continueRender(handle);
    };
    img.onerror = () => continueRender(handle);   // a missing tile must not hang the render
    img.src = tile.src.startsWith("http") ? tile.src : staticFile(tile.src);
  }, [tile, projection, width, height, handle]);

  // The drift. 1-2% across the whole shot: the map should feel alive without
  // the viewer being able to say it moved.
  const scale = 1 + drift * progress;

  return (
    <AbsoluteFill style={{ overflow: "hidden", opacity: ready ? 1 : 0 }}>
      <AbsoluteFill style={{ transform: `scale(${1 + drift}) translateX(${-drift * 40 * progress}%)` }}>
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{
            width: "100%",
            height: "100%",
            transform: `scale(${scale})`,
            // the land's own treatment: relief kept, colour pulled toward the film
            filter: `saturate(${GRADE.saturation * 0.62}) contrast(1.02) brightness(0.72)`,
          }}
        />
      </AbsoluteFill>

      {/* ocean: the palette floods everything outside the coastline */}
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ position: "absolute", inset: 0 }}
      >
        <defs>
          <mask id="terrain-ocean-mask">
            <rect width={width} height={height} fill="white" />
            <path d={landPath} fill="black" />
          </mask>
        </defs>
        <rect
          width={width}
          height={height}
          fill={SYS.bg}
          opacity={0.82}
          mask="url(#terrain-ocean-mask)"
        />
        <rect
          width={width}
          height={height}
          fill="#17202B"
          opacity={0.55}
          mask="url(#terrain-ocean-mask)"
        />
      </svg>

      {/* the film's own lift, so the map cuts against the photographs */}
      <AbsoluteFill style={{ background: GRADE.lift, opacity: 0.06 }} />
    </AbsoluteFill>
  );
};
