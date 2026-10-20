import React, { useLayoutEffect, useRef } from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';

export type Uniform =
  | ['1f' | '1i', string, number]
  | ['2f', string, [number, number]]
  | ['3f', string, [number, number, number]]
  | ['4f', string, [number, number, number, number]]
  | ['4fv', string, Float32Array | number[]];

type Gl = { gl: WebGL2RenderingContext; prog: WebGLProgram; locs: Map<string, WebGLUniformLocation | null> };

const VERT = `#version 300 es
in vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const init = (canvas: HTMLCanvasElement, frag: string): Gl => {
  const gl = canvas.getContext('webgl2', { premultipliedAlpha: true, preserveDrawingBuffer: true, antialias: false });
  if (!gl) throw new Error('Shader: WebGL2 is not available');
  const compile = (type: number, src: string) => {
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(`Shader compile: ${gl.getShaderInfoLog(s)}`);
    return s;
  };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, frag));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(`Shader link: ${gl.getProgramInfoLog(prog)}`);
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'aPos');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  return { gl, prog, locs: new Map() };
};

/**
 * A full-frame WebGL2 fragment shader. It always receives `uniform vec2 uRes`
 * (canvas size in px); pass the rest as uniforms. Output premultiplied alpha.
 * Use `GLSL_HEADER` + `GLSL_LIB` for shared helpers.
 */
export const Shader: React.FC<{ frag: string; uniforms: Uniform[]; style?: React.CSSProperties }> = ({ frag, uniforms, style }) => {
  const { width, height } = useVideoConfig();
  const ref = useRef<HTMLCanvasElement>(null);
  const glRef = useRef<Gl | null>(null);
  const key = JSON.stringify(uniforms.map(([t, n, v]) => [t, n, v instanceof Float32Array ? Array.from(v) : v]));

  useLayoutEffect(() => {
    if (!ref.current) return;
    if (!glRef.current) glRef.current = init(ref.current, frag);
    const { gl, prog, locs } = glRef.current;
    const loc = (n: string) => {
      if (!locs.has(n)) locs.set(n, gl.getUniformLocation(prog, n));
      return locs.get(n)!;
    };
    gl.viewport(0, 0, width, height);
    gl.uniform2f(loc('uRes'), width, height);
    for (const [type, name, v] of uniforms) {
      const l = loc(name);
      if (type === '1f') gl.uniform1f(l, v as number);
      else if (type === '1i') gl.uniform1i(l, v as number);
      else if (type === '2f') gl.uniform2fv(l, v as number[]);
      else if (type === '3f') gl.uniform3fv(l, v as number[]);
      else if (type === '4f') gl.uniform4fv(l, v as number[]);
      else gl.uniform4fv(l, v instanceof Float32Array ? v : new Float32Array(v as number[]));
    }
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, width, height]);

  return (
    <AbsoluteFill style={style}>
      <canvas ref={ref} width={width} height={height} style={{ width: '100%', height: '100%' }} />
    </AbsoluteFill>
  );
};

export const GLSL_HEADER = `#version 300 es
precision highp float;
uniform vec2 uRes;
out vec4 outColor;
`;

/** Shared GLSL helpers: hash, gradient noise, fbm, smooth min/max. */
export const GLSL_LIB = `
vec2 hash2(vec2 p, float s) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return -1.0 + 2.0 * fract(sin(p + s * 17.13) * 43758.5453);
}
float hash1(vec2 p, float s) { return fract(sin(dot(p, vec2(12.9898, 78.233)) + s * 3.17) * 43758.5453); }
float noise(vec2 p, float s) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(dot(hash2(i, s), f), dot(hash2(i + vec2(1, 0), s), f - vec2(1, 0)), u.x),
             mix(dot(hash2(i + vec2(0, 1), s), f - vec2(0, 1)), dot(hash2(i + vec2(1, 1), s), f - vec2(1, 1)), u.x), u.y) * 1.4;
}
float fbm(vec2 p, float s) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p, s + float(i) * 7.0); p = p * 2.03 + 11.0; a *= 0.5; }
  return v;
}
float smin(float a, float b, float k) { float h = max(k - abs(a - b), 0.0) / k; return min(a, b) - h * h * k * 0.25; }
float smax(float a, float b, float k) { return -smin(-a, -b, k); }
// Anti-aliased coverage of a signed distance (negative = inside).
float fill(float sdf) { float aa = max(fwidth(sdf) * 0.75, 0.25 / uRes.y); return 1.0 - smoothstep(-aa, aa, sdf); }
// Pixel position with y = 0..1 down the frame height, x = 0..aspect.
vec2 frameUv() { return vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y) / uRes.y; }
`;
