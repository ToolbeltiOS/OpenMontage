import React from "react";
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  continueRender,
  delayRender,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import {
  Bloom,
  BrightnessContrast,
  ChromaticAberration,
  EffectComposer,
  HueSaturation,
  Noise,
  Vignette,
} from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import * as THREE from "three";
import { SYS, gradeForAct } from "./design/system";

/**
 * The film look as a RENDER PASS, over finished frames.
 *
 * WHY A SECOND PASS AND NOT A LAYER
 * ---------------------------------
 * The CSS version is four stacked translucent divs — grain, vignette, a
 * chromatic offset, a wash. They composite, which is not the same as looking
 * at a photograph through a lens: a CSS vignette darkens the frame evenly
 * rather than falling off with the square of the distance, the grain is a
 * fixed tile that never moves with the image, and halation cannot exist at
 * all because no layer can see which pixels are bright.
 *
 * WebGL can see the frame, but only if the frame is a texture — and a Remotion
 * composition is DOM, which WebGL cannot sample. So this is a second pass over
 * the first pass's output: render the film with the CSS treatment OFF, then
 * run the result through here. That is what "as a render pass" has to mean in
 * a DOM renderer, and it has the useful property that the look can be changed
 * without re-rendering the film.
 *
 * COST
 * ----
 * Measured on the M1 with --gl=angle; see reports/film_look_cost.md. The brief
 * asked for it to stay inside +25% of the base render. It does not: the floor
 * is +79% and the full stack is +100%, about fifteen extra minutes on a
 * twenty-minute film. The numbers are recorded rather than the ceiling being
 * quietly moved.
 */

export interface FilmLookProps {
  /** the finished film, or a still, to run the pass over */
  src?: string;
  /** which act's grade to apply; the pass carries the same table as the DOM */
  act?: string | number;
  grain?: number;
  bloom?: number;
  distortion?: number;
  vignette?: number;
  /** a still instead of a video, for the comparison frames */
  isStill?: boolean;
  /**
   * How much of the chain to run. Measured per frame against the CSS
   * treatment on this machine — see reports/film_look_cost.md:
   *
   *   CSS treatment                                               24.4 ms
   *   minimal  grade + vignette + grain                            43.7 ms  +79%
   *   lean     + small-kernel bloom                                42.7 ms  +75%
   *   full     + mipmap bloom + radial chromatic aberration        48.9 ms  +100%
   *
   * The brief's ceiling is +25% and nothing here reaches it. The effect chain
   * is not the cost: going from minimal to full adds about 5 ms, while
   * getting a canvas, a full-frame plane and an EffectComposer running at all
   * costs about 19. So the floor of the approach is +79%, and the
   * configuration nearest it is the one with no halation in it — which was
   * the reason for doing this in a shader rather than in CSS.
   */
  stack?: "full" | "lean" | "minimal";
}

/** Fills the frame with the source texture, pixel for pixel. */
const SourcePlane: React.FC<{ texture: THREE.Texture }> = ({ texture }) => {
  const { viewport } = useThree();
  return (
    <mesh>
      <planeGeometry args={[viewport.width, viewport.height]} />
      <meshBasicMaterial map={texture} toneMapped={false} />
    </mesh>
  );
};

const useStillTexture = (src: string, enabled: boolean): THREE.Texture | null => {
  const [handle] = React.useState(() => (enabled ? delayRender("film look source") : null));
  const [tex, setTex] = React.useState<THREE.Texture | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!enabled) return;
    let live = true;
    new THREE.TextureLoader().load(
      src.startsWith("http") ? src : staticFile(src),
      (t) => {
        t.colorSpace = THREE.SRGBColorSpace;
        if (live) setTex(t);
      },
      undefined,
      () => {
        if (live) setFailed(true);
      },
    );
    return () => {
      live = false;
    };
  }, [src, enabled]);

  // Released only after a pass that had the texture — the same mistake as the
  // globe, which captured an untextured sphere when the release happened in
  // the loader callback.
  React.useEffect(() => {
    if (handle !== null && (tex || failed)) continueRender(handle);
  }, [tex, failed, handle]);

  return tex;
};

export const FilmLook: React.FC<FilmLookProps> = ({
  src = "doc/outro_hero.jpg",
  act,
  grain = 0.055,
  bloom = 0.5,
  distortion = 0.0016,
  vignette = 0.34,
  isStill = false,
  stack = "full",
}) => {
  const lean = stack !== "full";
  const bloomOn = stack !== "minimal";
  const { width, height } = useVideoConfig();
  const frame = useCurrentFrame();
  const g = gradeForAct(act);
  const texture = useStillTexture(src, isStill);

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg }}>
      {/* The source. A video is drawn by Remotion and sampled by the canvas
          below through its own DOM element; a still is loaded as a texture. */}
      {!isStill && (
        <AbsoluteFill style={{ opacity: 0 }}>
          <OffthreadVideo src={src.startsWith("http") ? src : staticFile(src)} />
        </AbsoluteFill>
      )}

      <ThreeCanvas
        width={width}
        height={height}
        camera={{ position: [0, 0, 5], fov: 50 }}
        gl={{ antialias: false }}
        style={{ backgroundColor: SYS.bg }}
      >
        {texture ? <SourcePlane texture={texture} /> : null}

        <EffectComposer>
          {/* the act's grade, in the pass rather than as a wash over it */}
          <HueSaturation saturation={g.saturation - 1} hue={0} />
          <BrightnessContrast brightness={g.lift * 0.4} contrast={0.04} />

          {/* halation: only the highlights bloom, which is the whole point —
              a CSS layer cannot know which pixels are bright */}
          <>
            {bloomOn ? (
              <Bloom
                intensity={lean ? bloom * 0.8 : bloom}
                luminanceThreshold={0.72}
                luminanceSmoothing={0.22}
                mipmapBlur={!lean}
                kernelSize={lean ? 2 : 3}
              />
            ) : (
              <></>
            )}
          </>

          {/* the lens: a small, constant offset rather than an animated one.
              Radial modulation is the single most expensive thing in the
              chain, so anything but the full stack does without it. */}
          <>
            {lean ? (
              <></>
            ) : (
              <ChromaticAberration
                offset={new THREE.Vector2(distortion, distortion * 0.6)}
                radialModulation
                modulationOffset={0.3}
              />
            )}
          </>

          <Vignette eskil={false} offset={0.28} darkness={vignette} />

          {/* grain last, so it sits on the image and not under the vignette */}
          <Noise premultiply={false} blendFunction={BlendFunction.OVERLAY} opacity={grain} />
        </EffectComposer>
      </ThreeCanvas>
    </AbsoluteFill>
  );
};

/**
 * The CSS treatment, full frame, as the film ships it today.
 *
 * Rendered as its own composition rather than as half of a split, because two
 * WebGL contexts on one frame do not survive the clip: the first attempt put
 * this beside <FilmLook> inside a clipPath and the shader half came out
 * black. The two halves are rendered separately and composited afterwards,
 * which is also the more honest comparison — each is produced by exactly the
 * pass that would ship it.
 */
export const CssLook: React.FC<{ src?: string; act?: string }> = ({
  src = "doc/outro_hero.jpg",
  act = "act3",
}) => {
  const g = gradeForAct(act);
  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg }}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          filter: `saturate(${g.saturation}) contrast(1.04)`,
        }}
      />
      {/* the stack as it ships: a wash, a radial vignette, a flat darken */}
      <AbsoluteFill
        style={{
          background:
            g.temperature >= 0
              ? "rgba(192,138,62,0.10)"
              : "rgba(38,52,74,0.16)",
          opacity: Math.abs(g.temperature) * 10,
          mixBlendMode: "screen",
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(70% 70% at 50% 50%, rgba(0,0,0,0) 52%, rgba(0,0,0,0.62) 100%)",
        }}
      />
      <AbsoluteFill style={{ background: "#07070A", opacity: 0.15 }} />
      <AbsoluteFill style={{ background: SYS.bg, opacity: g.lift }} />
    </AbsoluteFill>
  );
};
