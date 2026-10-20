import type React from 'react';
// Builders for CSS clip-path: path('...'). Coordinates are pixels of the frame.
// Sub-paths are unioned (all drawn with the same winding), so many shapes can
// make one mask.

export type Pt = [number, number];

const f = (n: number) => n.toFixed(1);

export const polyPath = (pts: Pt[]) =>
  pts.length ? `M${pts.map(([x, y]) => `${f(x)} ${f(y)}`).join('L')}Z` : '';

export const rectPath = (x: number, y: number, w: number, h: number) =>
  w <= 0 || h <= 0 ? '' : `M${f(x)} ${f(y)}H${f(x + w)}V${f(y + h)}H${f(x)}Z`;

export const circlePath = (cx: number, cy: number, r: number) =>
  r <= 0
    ? ''
    : `M${f(cx - r)} ${f(cy)}A${f(r)} ${f(r)} 0 1 0 ${f(cx + r)} ${f(cy)}A${f(r)} ${f(r)} 0 1 0 ${f(cx - r)} ${f(cy)}Z`;

/** Regular polygon or star (inner < 1 makes a star). */
export const starPath = (cx: number, cy: number, r: number, points: number, inner = 1, rotation = -Math.PI / 2) => {
  if (r <= 0) return '';
  const pts: Pt[] = [];
  const n = inner < 1 ? points * 2 : points;
  for (let i = 0; i < n; i++) {
    const rr = inner < 1 && i % 2 ? r * inner : r;
    const a = rotation + (i / n) * Math.PI * 2;
    pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]);
  }
  return polyPath(pts);
};

/** Pie slice from angle a0 to a1 (radians, clockwise from 12 o'clock). */
export const sectorPath = (cx: number, cy: number, r: number, a0: number, a1: number) => {
  if (a1 - a0 <= 0) return '';
  if (a1 - a0 >= Math.PI * 2 - 1e-4) return circlePath(cx, cy, r);
  const p = (a: number): Pt => [cx + Math.sin(a) * r, cy - Math.cos(a) * r];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M${f(cx)} ${f(cy)}L${f(x0)} ${f(y0)}A${f(r)} ${f(r)} 0 ${large} 1 ${f(x1)} ${f(y1)}Z`;
};

/** A style object that clips an element to the path. An empty path hides everything. */
export const clipStyle = (d: string): React.CSSProperties => ({ clipPath: `path('${d || 'M0 0Z'}')` });
