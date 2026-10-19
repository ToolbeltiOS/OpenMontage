import React, { useMemo } from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { geoMercator, geoPath, geoDistance } from "d3-geo";
import { feature } from "topojson-client";
import { SYS, TYPE, TRACK, EXPO_OUT, LAYOUT } from "../design/system";
import { SceneShell } from "../design/Scene";

export interface MapMarker {
  lon: number;
  lat: number;
  label: string;
  at: number;
  /** label offset in px */
  dx?: number;
  dy?: number;
}

export interface MapRouteProps {
  /** [lon, lat] pairs, in order of travel */
  route: [number, number][];
  markers?: MapMarker[];
  center?: [number, number];
  scale?: number;
  draw_seconds?: number;
  draw_at?: number;
  distance_callout?: { text: string; at: number };
  title?: string;
  kicker?: string;
  caption?: string;
  source?: string;
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
  /** great-circle style arc instead of straight segments */
  arc?: boolean;
  /**
   * Coastline detail. Defaults to "auto": 50m once the projection scale passes
   * 2000, 110m below it. 110m coastline falls apart on a regional map — Preseli
   * to Salisbury Plain renders at scale 5200 — and 50m is wasted on a
   * hemisphere.
   */
  detail?: "auto" | "110m" | "50m";
  /**
   * Draw modern national borders under the route. Off by default and it should
   * stay off for anything prehistoric: the film's maps are of landmasses and
   * sea routes, and a border drawn across them is an anachronism on screen.
   */
  borders?: boolean;
}

// world-atlas ships with the composer. Both resolutions are required
// statically so the bundler can see them; which one is drawn is chosen per
// scene from the projection scale.
/* eslint-disable @typescript-eslint/no-var-requires */
const land110 = require("world-atlas/land-110m.json");
const land50 = require("world-atlas/land-50m.json");
const countries50 = require("world-atlas/countries-50m.json");
/* eslint-enable @typescript-eslint/no-var-requires */

/** The scale above which 110m coastline starts to show its facets. */
export const DETAIL_SCALE_THRESHOLD = 2000;

/**
 * Route drawn over real geography. Used for the transport claims — Preseli to
 * Salisbury Plain, the Orcadian Basin sea route, ice-age coastlines.
 *
 * Land is a flat plate, not a texture: the drawn route is the only Hero
 * element, and the graticule-free coastline keeps the eye on it.
 */
export const MapRoute: React.FC<MapRouteProps> = ({
  route,
  markers = [],
  center,
  scale = 1400,
  draw_seconds = 2.6,
  draw_at = 0.4,
  distance_callout,
  title,
  kicker,
  caption,
  source,
  actNumber,
  actTitle,
  sceneIndex,
  coords,
  arc = false,
  detail = "auto",
  borders = false,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const resolution =
    detail === "auto" ? (scale > DETAIL_SCALE_THRESHOLD ? "50m" : "110m") : detail;

  const { pathD, projection, landPath, borderPath } = useMemo(() => {
    const c =
      center ??
      ([
        route.reduce((s, p) => s + p[0], 0) / route.length,
        route.reduce((s, p) => s + p[1], 0) / route.length,
      ] as [number, number]);
    const proj = geoMercator().center(c).scale(scale).translate([width / 2, height / 2]);
    const gp = geoPath(proj as any) as any;
    const atlas: any = resolution === "50m" ? land50 : land110;
    const land = feature(atlas, atlas.objects.land) as any;
    const line = { type: "LineString", coordinates: route } as any;
    const borderGeo = borders
      ? (feature(countries50 as any, (countries50 as any).objects.countries) as any)
      : null;
    return {
      pathD: gp(line) as string,
      projection: proj,
      landPath: gp(land) as string,
      borderPath: borderGeo ? (gp(borderGeo) as string) : null,
    };
  }, [route, center, scale, width, height, resolution, borders]);

  const drawStart = draw_at * fps;
  const p = interpolate(frame, [drawStart, drawStart + draw_seconds * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  const appear = (at: number, frames: number = SYS.unit) =>
    interpolate(frame, [at * fps, at * fps + frames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    });

  const km = useMemo(() => {
    let d = 0;
    for (let i = 1; i < route.length; i++) d += geoDistance(route[i - 1], route[i]) * 6371;
    return Math.round(d);
  }, [route]);

  const calloutP = distance_callout ? appear(distance_callout.at) : 0;

  return (
    <SceneShell
      background={SYS.bg}
      title={title}
      kicker={kicker}
      caption={caption ?? `great-circle length ≈ ${km} km`}
      source={source}
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      coords={coords}
    >
      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        <path d={landPath} fill="#16161B" stroke={SYS.rule} strokeWidth={1} />
        {borderPath ? (
          <path d={borderPath} fill="none" stroke={SYS.rule} strokeWidth={0.6} opacity={0.5} />
        ) : null}
        <path
          d={pathD}
          fill="none"
          stroke={SYS.accent}
          strokeWidth={3}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - p}
          style={arc ? { filter: "drop-shadow(0 0 7px rgba(192,138,62,0.30))" } : undefined}
        />
        {markers.map((m, i) => {
          const o = appear(m.at);
          if (o <= 0) return null;
          const xy = (projection as any)([m.lon, m.lat]);
          if (!xy) return null;
          return (
            <g key={i}>
              <circle cx={xy[0]} cy={xy[1]} r={6} fill={SYS.accent} opacity={o} />
              <circle
                cx={xy[0]}
                cy={xy[1]}
                r={16}
                fill="none"
                stroke={SYS.accent}
                strokeWidth={1.2}
                opacity={0.55}
                pathLength={1}
                strokeDasharray={1}
                strokeDashoffset={1 - o}
              />
              <text
                x={xy[0] + (m.dx ?? 24)}
                y={xy[1] + (m.dy ?? 7) + (1 - o) * SYS.rise}
                fill={SYS.text}
                fontFamily={SYS.label}
                fontSize={TYPE.labelSm}
                fontWeight={500}
                letterSpacing={TRACK}
                opacity={o}
                style={{
                  textTransform: "uppercase",
                  paintOrder: "stroke",
                  stroke: "rgba(12,12,14,0.85)",
                  strokeWidth: 6,
                }}
              >
                {m.label}
              </text>
            </g>
          );
        })}
      </svg>

      {distance_callout ? (
        <div
          style={{
            position: "absolute",
            right: LAYOUT.left,
            bottom: LAYOUT.bottom + 96,
            opacity: calloutP,
            filter: calloutP < 1 ? `blur(${(1 - calloutP) * SYS.blurFrom}px)` : undefined,
            transform: `translateY(${(1 - calloutP) * SYS.rise}px)`,
            background: "rgba(12,12,14,0.82)",
            borderLeft: `2px solid ${SYS.accent}`,
            padding: "14px 22px",
            color: SYS.text,
            fontFamily: SYS.data,
            fontSize: TYPE.data,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {distance_callout.text}
        </div>
      ) : null}
    </SceneShell>
  );
};
