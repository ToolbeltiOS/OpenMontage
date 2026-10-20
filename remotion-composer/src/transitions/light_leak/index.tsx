import React from 'react';
import { AbsoluteFill } from 'remotion';
import { bridged, GLSL_HEADER, GLSL_LIB, hexToRgb, paramDefaults, Shader } from '../core';
import meta from './transition.json';

type P = { colors: string[]; seed: number; hold: number };

// Intensity = soft blobs drifting in from the left + drifting noise, rising with t until it
// saturates everywhere. Colour ramps edge → middle → core with intensity. Screen-blended over the scene.
const FRAG = `${GLSL_HEADER}
uniform float uT;
uniform float uSeed;
uniform vec3 uC0;
uniform vec3 uC1;
uniform vec3 uC2;
${GLSL_LIB}
void main() {
  vec2 p = frameUv();
  float aspect = uRes.x / uRes.y;
  float I = 0.0;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    vec2 c = vec2(mix(-0.4, aspect * (0.5 + 0.4 * hash1(vec2(fi, 1.0), uSeed)), uT), 0.15 + 0.7 * hash1(vec2(fi, 2.0), uSeed) + 0.1 * sin(uT * 3.0 + fi));
    float r = 0.12 + 0.7 * uT * (0.6 + 0.6 * hash1(vec2(fi, 3.0), uSeed));
    vec2 d = (p - c) / vec2(1.6, 1.0);
    I += exp(-dot(d, d) / (r * r)) * (0.3 + 0.6 * uT);
  }
  I *= 0.75 + 0.5 * fbm(p * 2.0 + vec2(uT * 0.8, 0.0), uSeed);
  I += smoothstep(0.7, 1.0, uT) * 2.5;
  I *= smoothstep(0.0, 0.08, uT);
  vec3 col = mix(uC0, uC1, smoothstep(0.0, 0.6, I));
  col = mix(col, uC2, smoothstep(0.6, 1.3, I));
  float a = clamp(I, 0.0, 1.0);
  outColor = vec4(col * a, a);
}
`;

const Leak: React.FC<{ t: number; seed: number; colors: string[] }> = ({ t, seed, colors }) => (
  <Shader
    style={{ mixBlendMode: 'screen' }}
    frag={FRAG}
    uniforms={[['1f', 'uT', t], ['1f', 'uSeed', seed], ['3f', 'uC0', hexToRgb(colors[0])], ['3f', 'uC1', hexToRgb(colors[1] ?? colors[0])], ['3f', 'uC2', hexToRgb(colors[2] ?? colors[1] ?? colors[0])]]}
  />
);

export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params }) =>
  phase === 'in' ? <Leak t={progress} seed={params.seed} colors={params.colors} /> : <Leak t={1 - progress} seed={params.seed + 1} colors={params.colors} />,
);
