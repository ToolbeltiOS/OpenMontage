import { random } from 'remotion';

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
/** 0..1 position of p inside [a, b], clamped. */
export const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a));
export const mix = (a: number, b: number, t: number) => a + (b - a) * t;

export const ease = {
  linear: (t: number) => t,
  inCubic: (t: number) => t * t * t,
  outCubic: (t: number) => 1 - Math.pow(1 - t, 3),
  inOutCubic: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  inQuint: (t: number) => t ** 5,
  outQuint: (t: number) => 1 - Math.pow(1 - t, 5),
  inOutQuint: (t: number) => (t < 0.5 ? 16 * t ** 5 : 1 - Math.pow(-2 * t + 2, 5) / 2),
  inOutExpo: (t: number) =>
    t <= 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2,
  outBack: (t: number) => 1 + 2.70158 * Math.pow(t - 1, 3) + 1.70158 * Math.pow(t - 1, 2),
  inBack: (t: number) => 2.70158 * t * t * t - 1.70158 * t * t,
};

export const hexToRgb = (hex: string): [number, number, number] => {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const n = parseInt(h, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};

/** Deterministic random in [0, 1) for a seed and any number of keys. */
export const rand = (seed: number, ...keys: (string | number)[]) => random(`${seed}:${keys.join(':')}`);

/** Smooth deterministic 1D noise in [-1, 1]. */
export const noise1 = (x: number, seed = 0) => {
  const i = Math.floor(x);
  const f = x - i;
  const u = f * f * (3 - 2 * f);
  const a = rand(seed, 'n1', i) * 2 - 1;
  const b = rand(seed, 'n1', i + 1) * 2 - 1;
  return a + (b - a) * u;
};

/** Fractal 1D noise in roughly [-1, 1]. */
export const fbm1 = (x: number, seed = 0, octaves = 3) => {
  let v = 0;
  let amp = 0.5;
  let freq = 1;
  for (let o = 0; o < octaves; o++) {
    v += amp * noise1(x * freq, seed + o * 17);
    amp *= 0.5;
    freq *= 2.1;
  }
  return v * 1.6;
};
