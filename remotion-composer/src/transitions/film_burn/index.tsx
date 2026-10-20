import React from 'react';
import { useCurrentFrame } from 'remotion';
import { bridged, GLSL_HEADER, GLSL_LIB, hexToRgb, paramDefaults, Shader } from '../core';
import meta from './transition.json';

type P = { glow: string; core: string; seed: number; hold: number };

// Burn holes: noisy circles that grow from scattered spots. Inside: the white-hot core. Just outside
// the edge: a glowing band, then a faint scorch. The core flickers slightly per frame like old film.
const FRAG = `${GLSL_HEADER}
uniform float uT;
uniform float uSeed;
uniform float uFlicker;
uniform vec3 uGlow;
uniform vec3 uCore;
${GLSL_LIB}
void main() {
  vec2 p = frameUv();
  float aspect = uRes.x / uRes.y;
  float sdf = 1e3;
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    vec2 c = vec2(hash1(vec2(fi, 1.0), uSeed) * aspect, hash1(vec2(fi, 2.0), uSeed));
    float birth = hash1(vec2(fi, 3.0), uSeed) * 0.4;
    float s = clamp((uT - birth) / (1.0 - birth), 0.0, 1.0);
    float r = 1.5 * pow(s, 1.7);
    if (s <= 0.0) continue;
    sdf = min(sdf, length(p - c) - r + fbm(p * 5.0 + fi, uSeed) * 0.12 * min(1.0, r * 4.0));
  }
  sdf -= smoothstep(0.85, 1.0, uT) * 3.0;
  if (uT <= 0.0) sdf = 1.0;
  float core = fill(sdf);
  float glow = exp(-max(sdf, 0.0) * 40.0) * step(-0.001, sdf) * smoothstep(0.0, 0.05, uT);
  float scorch = exp(-max(sdf, 0.0) * 12.0) * 0.35 * smoothstep(0.0, 0.05, uT);
  vec3 col = uCore * uFlicker;
  float a = core;
  col = mix(vec3(0.08, 0.03, 0.0), col, core);
  a = max(a, scorch * (1.0 - core));
  col = mix(col, uGlow * 1.2, glow * (1.0 - core));
  a = max(a, glow);
  outColor = vec4(col * a, a);
}
`;

const Burn: React.FC<{ t: number; seed: number; params: P }> = ({ t, seed, params }) => {
  const frame = useCurrentFrame();
  const flicker = 0.93 + 0.07 * Math.sin(frame * 12.9898 + seed);
  return (
    <Shader frag={FRAG} uniforms={[['1f', 'uT', t], ['1f', 'uSeed', seed], ['1f', 'uFlicker', flicker], ['3f', 'uGlow', hexToRgb(params.glow)], ['3f', 'uCore', hexToRgb(params.core)]]} />
  );
};

export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params }) =>
  phase === 'in' ? <Burn t={progress} seed={params.seed} params={params} /> : <Burn t={1 - progress} seed={params.seed + 1} params={params} />,
);
