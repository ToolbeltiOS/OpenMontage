import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing, staticFile, delayRender, continueRender } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { SYS, EXPO_IN_OUT, GRADE } from "../design/system";

export interface GlobeDescentProps {
  /** where the descent lands, in degrees */
  lon: number;
  lat: number;
  /** seconds the descent takes; the brief's band is 3-4 */
  seconds?: number;
  /** the 2D map this hands off to */
  children?: React.ReactNode;
  /** seconds of crossfade into the handoff */
  handoff_seconds?: number;
  texture?: string;
}

const RADIUS = 1;
/** Far enough that the whole disc sits inside the frame with air around it. */
const START_DISTANCE = 3.4;
/** Close enough that the curve has left the frame and the map can take over. */
const END_DISTANCE = 1.08;

/**
 * The point on a unit sphere that an equirectangular texture puts (lon, lat)
 * at, for three.js's own SphereGeometry winding.
 */
const onSphere = (lon: number, lat: number): THREE.Vector3 => {
  const phi = THREE.MathUtils.degToRad(90 - lat);
  const theta = THREE.MathUtils.degToRad(lon + 180);
  return new THREE.Vector3(
    -Math.sin(phi) * Math.cos(theta),
    Math.cos(phi),
    Math.sin(phi) * Math.sin(theta),
  );
};

/**
 * Move the CAMERA onto the ray through the target and look back at the centre.
 *
 * Rotating the globe instead meant deriving the texture's own orientation from
 * three.js's sphere winding, and the first attempt put Antarctica and Australia
 * in frame on a descent to Scotland. Aiming the camera needs no such derivation:
 * the point is where the point is.
 */
const AimedCamera: React.FC<{ lon: number; lat: number; distance: number }> = ({
  lon, lat, distance,
}) => {
  const camera = useThree((s) => s.camera);
  const target = React.useMemo(() => onSphere(lon, lat), [lon, lat]);
  camera.position.copy(target).multiplyScalar(distance);
  camera.up.set(0, 1, 0);
  camera.lookAt(0, 0, 0);
  camera.updateProjectionMatrix();
  return null;
};

const Globe: React.FC<{ lon: number; lat: number; t: number; map: THREE.Texture | null; distance: number }> = ({
  lon, lat, t, map, distance,
}) => {
  return (
    <group>
      <AimedCamera lon={lon} lat={lat} distance={distance} />
      <mesh>
        <sphereGeometry args={[RADIUS, 96, 96]} />
        {map ? (
          <meshStandardMaterial
            map={map}
            roughness={1}
            metalness={0}
            // the film's grade, applied to the sphere rather than over it, so
            // the terminator does not look like a filter sitting on glass
            color={new THREE.Color(0.62, 0.63, 0.60)}
          />
        ) : (
          <meshStandardMaterial color={new THREE.Color(0.06, 0.06, 0.07)} />
        )}
      </mesh>
      {/* a single low sun, raking across the target so the limb reads as a
          sphere rather than a disc */}
      <directionalLight
        position={onSphere(lon + 55, lat + 18).multiplyScalar(4)}
        intensity={2.4 + t * 0.5}
      />
      <ambientLight intensity={0.3} />
    </group>
  );
};

/**
 * Load the texture OUTSIDE the canvas.
 *
 * Loading it inside, with delayRender released from the loader callback,
 * rendered an untextured grey sphere: react-three-fiber commits on its own
 * loop, and the frame was captured before the material had the map. Resolving
 * it in the parent means the canvas is only ever mounted with a texture in
 * hand.
 */
const useGlobeTexture = (src: string): THREE.Texture | null => {
  const [handle] = React.useState(() => delayRender("globe texture"));
  const [map, setMap] = React.useState<THREE.Texture | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    let live = true;
    new THREE.TextureLoader().load(
      src.startsWith("http") ? src : staticFile(src),
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        if (live) setMap(tex);
      },
      undefined,
      () => {
        if (live) setFailed(true);   // a missing texture must not hang the render
      },
    );
    return () => {
      live = false;
    };
  }, [src]);

  // Released in its OWN effect, keyed on the texture, so the render is only
  // let go after a pass that actually had it. Releasing in the loader
  // callback — the same tick as the state update — captured an untextured
  // grey sphere whenever the file was not already in Chrome's cache, which
  // made it look intermittent rather than wrong.
  React.useEffect(() => {
    if (map || failed) continueRender(handle);
  }, [map, failed, handle]);

  return map;
};

/**
 * A descent from a dark globe to one place, handing off to the 2D map.
 *
 * The brief's ask, and the reason it is a separate component rather than a
 * mode of MapRoute: the globe is three-dimensional and the map is not, so
 * they are two renderers. This one owns the descent and then dissolves into
 * whatever it is given as children — normally the MapRoute for the same
 * extent, which means the handoff lands on the same geography at the same
 * scale rather than cutting to a different drawing of it.
 *
 * Runs on WebGL and therefore needs `--gl=angle` on an M1, the same
 * requirement as the shader film look.
 */
export const GlobeDescent: React.FC<GlobeDescentProps> = ({
  lon,
  lat,
  seconds = 3.5,
  children,
  handoff_seconds = 0.6,
  texture = "basemaps/world.jpg",
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = Math.min(frame / (seconds * fps), 1);
  const map = useGlobeTexture(texture);

  const distance = interpolate(t, [0, 1], [START_DISTANCE, END_DISTANCE], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  // The handoff starts before the descent ends, so the map is already there
  // when the curve leaves the frame.
  const handoffStart = (seconds - handoff_seconds) * fps;
  const handoff = interpolate(frame, [handoffStart, seconds * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_IN_OUT),
  });

  return (
    <AbsoluteFill style={{ backgroundColor: SYS.bg }}>
      <AbsoluteFill style={{ opacity: 1 - handoff }}>
        <ThreeCanvas
          width={width}
          height={height}
          camera={{ fov: 42, position: [0, 0, distance] }}
          gl={{ antialias: true }}
          style={{ backgroundColor: SYS.bg }}
        >
          <Globe lon={lon} lat={lat} t={t} map={map} distance={distance} />
        </ThreeCanvas>
      </AbsoluteFill>

      {children ? (
        <AbsoluteFill style={{ opacity: handoff }}>{children}</AbsoluteFill>
      ) : null}

      {/* the film's grain and lift, over both halves of the handoff */}
      <AbsoluteFill
        style={{ background: GRADE.lift, opacity: 0.05, pointerEvents: "none" }}
      />
    </AbsoluteFill>
  );
};
