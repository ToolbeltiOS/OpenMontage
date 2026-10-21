import React from "react";
import {
  AbsoluteFill,
  Img,
  Video,
  staticFile,
  useCurrentFrame,
  useDelayRender,
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
import { SYS, gradeOps } from "./design/system";

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
  /**
   * For a pass over a whole film: which act is on screen when. The grade is
   * per act and the pass is per composition, so without this a twenty-minute
   * film would be graded as whichever act was named first.
   */
  acts?: { act: string; from_seconds: number; to_seconds: number }[];
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

/**
 * Fills the frame with the source texture, pixel for pixel, carrying the
 * grade's multiply and brightness on the material — which is the same linear
 * multiply the CSS path does with `brightness()` and a multiply-blended tint.
 */
const SourcePlane: React.FC<{ texture: THREE.Texture; tint: THREE.Color }> = ({
  texture, tint,
}) => {
  const { viewport } = useThree();
  return (
    <mesh>
      <planeGeometry args={[viewport.width, viewport.height]} />
      <meshBasicMaterial map={texture} color={tint} toneMapped={false} />
    </mesh>
  );
};

/**
 * The source texture, gated by Remotion's own <Img> rather than by a loader
 * of ours.
 *
 * Three versions of this raced and lost. Releasing delayRender in the loader
 * callback captured an empty plane; releasing it in an effect keyed on the
 * texture still lost under load; two requestAnimationFrames still produced a
 * black frame in three of six comparison renders. Remotion already blocks the
 * frame until an <Img> has decoded, so the image element it has finished with
 * is wrapped as a texture instead of fetching the same file twice. One
 * guarantee, and it is the renderer's own.
 */
/**
 * The same idea for a moving source.
 *
 * `OffthreadVideo` extracts frames outside the DOM, so there is no element for
 * WebGL to sample — the first version of this pass rendered an invisible
 * OffthreadVideo and a canvas with nothing in it. `Video` mounts a real
 * element and Remotion seeks it to the current frame before the capture, so a
 * VideoTexture over it samples the right frame.
 */
const useVideoTexture = (src: string, enabled: boolean) => {
  const frame = useCurrentFrame();
  const [el, setEl] = React.useState<HTMLVideoElement | null>(null);
  const texture = React.useMemo(() => {
    if (!el) return null;
    const t = new THREE.VideoTexture(el);
    t.colorSpace = THREE.SRGBColorSpace;
    t.minFilter = THREE.LinearFilter;
    return t;
  }, [el]);

  // The element is seeked per frame, so the texture has to be told each time.
  React.useEffect(() => {
    if (texture) texture.needsUpdate = true;
  }, [texture, frame]);

  const video = enabled ? (
    <Video
      src={src.startsWith("http") ? src : staticFile(src)}
      ref={(node) => setEl(node)}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0 }}
      muted
    />
  ) : null;

  return { texture, video };
};

/**
 * The source texture for the frame the renderer is actually asking for.
 *
 * WHY THIS IS A BARRIER AND NOT A LOADER
 * --------------------------------------
 * `<ThreeCanvas>` draws exactly once per frame: in rendering mode its
 * frameloop is "never", and an internal `ManualFrameRenderer` calls
 * `advance()` from an effect keyed on `useCurrentFrame()`. So the canvas is
 * drawn in the same commit in which the frame number changed — which is
 * BEFORE the image for that frame has decoded, because decoding is
 * asynchronous and the element arrives afterwards through React state.
 *
 * Nothing then redraws. The frame number does not change again until the next
 * frame, so the capture keeps whatever the last draw left in the backing
 * store: the texture of an EARLIER frame. Over a sequence that is not a
 * uniform delay but a permutation, because how many images happen to have
 * decoded between two draws varies. Measured on a sequence with its own index
 * burned into every frame as ten high-contrast bits: 118 of 120 output frames
 * carried the wrong source frame, lagging three to five and locally shuffled,
 * and one carried a torn upload belonging to no source frame at all.
 *
 * Marking the texture `needsUpdate` every frame — the previous fix, for the
 * different bug where the GPU kept the first upload forever — cannot help: a
 * texture marked for upload with no draw after it is never uploaded.
 *
 * So the frame is held until the texture for THIS src exists and the canvas
 * has been drawn with it. `<DrawWhenReady>` sits inside the canvas and draws
 * on texture identity rather than on frame number; the handle is released
 * from here, a parent, whose effects React runs after its children's. That
 * ordering is the guarantee — not a timer and not a pair of
 * requestAnimationFrames, both of which were tried here and both of which
 * lost under load.
 *
 * If the image never arrives the handle times out and the render fails, which
 * is the intended behaviour: a loud failure beats a silently wrong frame.
 */
const DrawWhenReady: React.FC<{
  texture: THREE.Texture | null;
  onDrawn: () => void;
}> = ({ texture, onDrawn }) => {
  const advance = useThree((state) => state.advance);
  React.useEffect(() => {
    if (!texture) return;
    texture.needsUpdate = true;
    advance(performance.now());
    onDrawn();
  }, [texture, advance, onDrawn]);
  return null;
};

const useImgTexture = (src: string, enabled: boolean) => {
  const { delayRender, continueRender } = useDelayRender();
  // The element is carried together with the src it belongs to, so a texture
  // is never built from the previous frame's image. `loaded.src !== src` is
  // the whole check, and it is the reason this cannot lag.
  const [loaded, setLoaded] = React.useState<
    { src: string; el: HTMLImageElement } | null
  >(null);

  const texture = React.useMemo(() => {
    if (!loaded || loaded.src !== src) return null;
    const t = new THREE.Texture(loaded.el);
    t.colorSpace = THREE.SRGBColorSpace;
    t.needsUpdate = true;
    return t;
  }, [loaded, src]);

  const handle = React.useRef<number | null>(null);
  React.useLayoutEffect(() => {
    if (!enabled) return;
    const h = delayRender(`film look: the frame for ${src}`);
    handle.current = h;
    return () => {
      // Only if this frame never drew — a stalled render is a failure we want
      // to see, but a handle left open on unmount would hang the whole job.
      if (handle.current === h) {
        handle.current = null;
        continueRender(h);
      }
    };
  }, [src, enabled, delayRender, continueRender]);

  const onDrawn = React.useCallback(() => {
    if (handle.current === null) return;
    const h = handle.current;
    handle.current = null;
    continueRender(h);
  }, [continueRender]);

  // onLoad, not a ref: a ref fires on mount, before the image has decoded,
  // and a THREE.Texture built from an incomplete element uploads nothing and
  // never updates. `key` remounts the element per src, so onLoad fires again
  // on a sequence, where React would otherwise keep one <img> node and never
  // re-notify.
  const img = enabled ? (
    <Img
      key={src}
      src={src.startsWith("http") ? src : staticFile(src)}
      onLoad={(e) => setLoaded({ src, el: e.currentTarget })}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0 }}
    />
  ) : null;

  return { texture, img, onDrawn };
};

export const FilmLook: React.FC<FilmLookProps> = ({
  src = "doc/outro_hero.jpg",
  act,
  grain = 0.055,
  bloom = 0.5,
  distortion = 0.0016,
  // 0.85 is where the shader's mean luminance lands within 2% of the CSS
  // path's on the same plate. The two vignettes still FALL OFF differently —
  // that is the look being compared — but they no longer differ in level.
  vignette = 0.85,
  isStill = false,
  stack = "full",
  acts,
}) => {
  const lean = stack !== "full";
  const bloomOn = stack !== "minimal";
  const { width, height, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const t = frame / fps;
  const activeAct =
    acts?.find((a) => t >= a.from_seconds && t < a.to_seconds)?.act ?? act;
  const g = gradeOps(activeAct);
  const { texture: stillTexture, img, onDrawn } = useImgTexture(src, isStill);
  const { texture: videoTexture, video } = useVideoTexture(src, !isStill);
  const texture = isStill ? stillTexture : videoTexture;
  const tint = React.useMemo(
    () => new THREE.Color(
      g.multiply[0] * g.brightness,
      g.multiply[1] * g.brightness,
      g.multiply[2] * g.brightness,
    ),
    [g.multiply, g.brightness],
  );

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg }}>
      {/* The source. Remotion blocks the frame until this has decoded; the
          canvas below samples the element it finished with. */}
      {img}
      {video}

      <ThreeCanvas
        width={width}
        height={height}
        camera={{ position: [0, 0, 5], fov: 50 }}
        gl={{ antialias: false }}
        style={{ backgroundColor: SYS.bg }}
      >
        {texture ? <SourcePlane texture={texture} tint={tint} /> : null}
        {/* draws on texture identity, then releases the frame */}
        {isStill ? <DrawWhenReady texture={texture} onDrawn={onDrawn} /> : null}

        <EffectComposer>
          {/* the act's grade. The multiply and brightness are already on the
              plane; these two finish the same chain the CSS path runs. */}
          <HueSaturation saturation={g.saturation - 1} hue={0} />
          <BrightnessContrast brightness={0} contrast={g.contrast - 1} />

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
/**
 * The pass over a rendered frame SEQUENCE.
 *
 * A video source needs an element WebGL can sample, and neither of Remotion's
 * video components provides one that survives a per-frame seek:
 * OffthreadVideo extracts frames outside the DOM entirely, and a VideoTexture
 * over <Video> sampled black. A frame sequence sidesteps the question — each
 * frame is a still, and the still path is the one that renders the same
 * numbers three times in a row.
 *
 * It costs disk: 90 seconds at 1080p is about 350 MB of JPEG. They are
 * deleted after the encode.
 */
export const FilmLookFrames: React.FC<{
  dir?: string;
  act?: string;
  stack?: "full" | "lean" | "minimal";
  acts?: { act: string; from_seconds: number; to_seconds: number }[];
}> = ({ dir = "demoframes", act = "act2", stack = "full", acts }) => {
  const frame = useCurrentFrame();
  const name = String(frame + 1).padStart(5, "0");
  return (
    <FilmLook src={`${dir}/f_${name}.jpg`} act={act} stack={stack} acts={acts} isStill />
  );
};

export const CssLook: React.FC<{ src?: string; act?: string }> = ({
  src = "doc/outro_hero.jpg",
  act = "act3",
}) => {
  const g = gradeOps(act);
  const rgb = (c: readonly number[]) =>
    `rgb(${c.map((v) => Math.round(Math.min(1, v) * 255)).join(",")})`;
  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg }}>
      {/* the identical chain: multiply, then saturate, then contrast */}
      <AbsoluteFill style={{ isolation: "isolate" }}>
        <Img
          src={staticFile(src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: `brightness(${g.brightness}) saturate(${g.saturation}) contrast(${g.contrast})`,
          }}
        />
        <AbsoluteFill
          style={{ background: rgb(g.multiply), mixBlendMode: "multiply" }}
        />
      </AbsoluteFill>

      {/* and then the one layer the shader actually replaces: a radial
          gradient that darkens evenly, against a vignette that falls off with
          distance. Matched in strength, so what differs is the falloff. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(70% 70% at 50% 50%, rgba(0,0,0,0) 52%, rgba(0,0,0,0.62) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
