import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadSpaceGrotesk } from "./lib/localFonts";
import { TextCard } from "./components/TextCard";
import { StatCard } from "./components/StatCard";
import { CalloutBox } from "./components/CalloutBox";
import { ComparisonCard } from "./components/ComparisonCard";
import { BarChart } from "./components/charts/BarChart";
import { LineChart } from "./components/charts/LineChart";
import { PieChart } from "./components/charts/PieChart";
import { KPIGrid } from "./components/charts/KPIGrid";
import { ProgressBar } from "./components/ProgressBar";
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";
import { DocCaption } from "./design/DocCaption";
import { EmphasisLine } from "./design/Emphasis";
import { Graded, FrameLayer } from "./design/Frame";
import { SourceCaption } from "./design/Scene";
import { ActTitleCard } from "./scenes/ActTitleCard";
import { EvidenceCard } from "./scenes/EvidenceCard";
import { ScaleComparison } from "./scenes/ScaleComparison";
import { OutroCta } from "./scenes/OutroCta";
import { SectionTitle } from "./components/SectionTitle";
import { StatReveal } from "./components/StatReveal";
import { HeroTitle } from "./components/HeroTitle";
import { AnimeScene } from "./components/AnimeScene";
import type { CameraMotion } from "./components/AnimeScene";
import { TerminalScene } from "./components/TerminalScene";
import type { TerminalStep } from "./components/TerminalScene";
import { ScreenshotScene } from "./components/ScreenshotScene";
import { AnnotatedStill } from "./components/AnnotatedStill";
import { Schematic } from "./components/Schematic";
import { MapRoute } from "./components/MapRoute";
import { Timeline } from "./components/Timeline";
import { DocumentReveal } from "./components/DocumentReveal";
import type { ScreenshotStep } from "./components/ScreenshotScene";
import { ProviderChip } from "./components/ProviderChip";
import { resolveAsset } from "./lib/resolveAsset";
import type { ParticleType } from "./components/ParticleOverlay";
import { resolveTheme, type ThemeConfig, DEFAULT_THEME } from "./Root";

// Load Space Grotesk font for cinematic typography
const { fontFamily } = loadSpaceGrotesk(["400", "700"]);

// ---------------------------------------------------------------------------
// Animated Background — Gradient Mesh + Floating Orbs
// ---------------------------------------------------------------------------

// Parse hex color to RGB components
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.replace("#", "");
  const bigint = parseInt(clean.length === 3
    ? clean.split("").map(c => c + c).join("")
    : clean, 16);
  return { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 };
}

// Detect if a color is "light" (for choosing grid/overlay treatment)
function isLightColor(hex: string): boolean {
  const { r, g, b } = hexToRgb(hex);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128;
}

// Scrim painted behind a hero title. It has to wash *away* from the theme's
// text color: a dark scrim under a light theme's dark text drops the pair to
// ~3.4:1, which is the same legibility bug in reverse.
function heroScrim(theme: ThemeConfig): string {
  const { r, g, b } = hexToRgb(
    isLightColor(theme.backgroundColor) ? "#FFFFFF" : "#0F172A"
  );
  return (
    `radial-gradient(ellipse at center, rgba(${r},${g},${b},0.35) 0%, ` +
    `rgba(${r},${g},${b},0.55) 100%)`
  );
}

// Darken/lighten a color by mixing toward black or white
function shiftColor(hex: string, amount: number): string {
  const { r, g, b } = hexToRgb(hex);
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  if (amount < 0) {
    // Darken
    const f = 1 + amount;
    return `rgb(${clamp(r * f)}, ${clamp(g * f)}, ${clamp(b * f)})`;
  }
  // Lighten
  return `rgb(${clamp(r + (255 - r) * amount)}, ${clamp(g + (255 - g) * amount)}, ${clamp(b + (255 - b) * amount)})`;
}

const AnimatedBackground: React.FC<{ theme: ThemeConfig }> = ({ theme }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const bg = theme.backgroundColor;
  const primary = theme.primaryColor;
  const accent = theme.accentColor;
  const surface = theme.surfaceColor;
  const light = isLightColor(bg);

  // Slow-moving gradient angles
  const angle1 = 135 + Math.sin(frame / (fps * 8)) * 30;

  // Build gradient from theme colors instead of hardcoded dark blue
  const { r: bgR, g: bgG, b: bgB } = hexToRgb(bg);
  const { r: priR, g: priG, b: priB } = hexToRgb(primary);
  const { r: accR, g: accG, b: accB } = hexToRgb(accent);

  const gradient = `
    radial-gradient(ellipse at ${30 + Math.sin(frame / (fps * 10)) * 20}% ${40 + Math.cos(frame / (fps * 8)) * 20}%,
      rgba(${priR}, ${priG}, ${priB}, 0.15) 0%, transparent 60%),
    radial-gradient(ellipse at ${70 + Math.cos(frame / (fps * 7)) * 20}% ${60 + Math.sin(frame / (fps * 9)) * 25}%,
      rgba(${accR}, ${accG}, ${accB}, 0.1) 0%, transparent 55%),
    linear-gradient(${angle1}deg, ${bg} 0%, ${shiftColor(bg, light ? -0.05 : 0.05)} 40%, ${surface} 70%, ${bg} 100%)
  `;

  // Floating orbs — derived from theme chart colors with low opacity
  const orbColors = theme.chartColors.slice(0, 5);
  const orbOpacity = light ? 0.06 : 0.08;
  const orbs = [
    { x: 20, y: 30, size: 300, color: orbColors[0] || primary, speedX: 7, speedY: 11 },
    { x: 70, y: 60, size: 250, color: orbColors[1] || accent, speedX: 9, speedY: 8 },
    { x: 40, y: 80, size: 200, color: orbColors[2] || primary, speedX: 13, speedY: 6 },
    { x: 80, y: 20, size: 350, color: orbColors[3] || accent, speedX: 11, speedY: 14 },
    { x: 10, y: 70, size: 180, color: orbColors[4] || primary, speedX: 8, speedY: 10 },
  ];

  // Grid and overlay colors adapt to light vs dark backgrounds
  const gridColor = light ? "rgba(0,0,0,0.03)" : "rgba(255,255,255,0.02)";
  const fadeColor = light
    ? `rgba(${bgR},${bgG},${bgB},0.2)`
    : `rgba(${bgR},${bgG},${bgB},0.4)`;

  return (
    <AbsoluteFill style={{ background: gradient }}>
      {/* Floating glow orbs */}
      {orbs.map((orb, i) => {
        const ox = orb.x + Math.sin(frame / (fps * orb.speedX)) * 15;
        const oy = orb.y + Math.cos(frame / (fps * orb.speedY)) * 12;
        const { r, g, b } = hexToRgb(orb.color);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${ox}%`,
              top: `${oy}%`,
              width: orb.size,
              height: orb.size,
              borderRadius: "50%",
              background: `rgba(${r}, ${g}, ${b}, ${orbOpacity})`,
              filter: `blur(${orb.size * 0.4}px)`,
              transform: "translate(-50%, -50%)",
              willChange: "transform",
            }}
          />
        );
      })}

      {/* Subtle grid overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(${gridColor} 1px, transparent 1px),
            linear-gradient(90deg, ${gridColor} 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          opacity: 0.5 + Math.sin(frame / (fps * 20)) * 0.2,
        }}
      />

      {/* Top gradient fade for depth */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "30%",
          background: `linear-gradient(to bottom, ${fadeColor}, transparent)`,
        }}
      />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Types — aligned with edit_decisions artifact schema
// ---------------------------------------------------------------------------

export interface Cut {
  id: string;
  source: string;
  in_seconds: number;
  out_seconds: number;
  layer?: string;
  type?: string;
  // Component-specific props
  text?: string;
  stat?: string;
  subtitle?: string;
  callout_type?: "info" | "warning" | "tip" | "quote";
  title?: string;
  // Video source trim — seek to this point in the source before playback.
  // Defaults to 0 (play from beginning). Use this instead of in_seconds for source trimming.
  source_in_seconds?: number;
  // Comparison props
  leftLabel?: string;
  rightLabel?: string;
  leftValue?: string;
  rightValue?: string;
  // Chart props
  chartData?: any[];
  chartSeries?: any[];
  chartColors?: string[];
  chartAnimation?: string;
  donut?: boolean;
  centerLabel?: string;
  centerValue?: string;
  showGrid?: boolean;
  showValues?: boolean;
  showLegend?: boolean;
  showMarkers?: boolean;
  xLabel?: string;
  yLabel?: string;
  columns?: 2 | 3 | 4;
  // Progress bar props
  progress?: number;
  progressLabel?: string;
  progressColor?: string;
  progressAnimation?: string;
  progressSegments?: any[];
  // Hero title props (when used as scene, not overlay)
  heroSubtitle?: string;
  // wak3up-documentary component props
  annotations?: any[];
  measurement?: any;
  cutaway?: any;
  caption?: string;
  parallax?: boolean;
  layers?: any[];
  reveals?: any[];
  labels?: any[];
  viewBox?: string;
  route?: [number, number][];
  markers?: any[];
  center?: [number, number];
  scale?: number;
  draw_seconds?: number;
  draw_at?: number;
  distance_callout?: any;
  arc?: boolean;
  events?: any[];
  orientation?: "horizontal" | "vertical";
  span?: [number, number];
  playhead?: boolean;
  headline?: string;
  lines?: any[];
  sourceLine?: string;
  paper?: "light" | "dark";
  light_sweep?: boolean;
  sweep_at?: number;
  dim?: number;
  // Persistent frame layer — carried by every documentary scene
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  coords?: string;
  kicker?: string;
  // act_title_card
  act?: string;
  epigraph?: string;
  fade_in?: number;
  fade_out?: number;
  // evidence_card
  claim?: string;
  attribution?: string;
  detail?: string;
  status?: "peer_reviewed" | "contested" | "unpublished" | "measured" | "claim";
  index?: string;
  // outro_cta
  like_at?: number;
  subscribe_at?: number;
  subscribe_label?: string;
  // scale_comparison
  items?: any[];
  unit?: string;
  decimals?: number;
  footnote?: string;
  at?: number;
  // Styling overrides
  backgroundColor?: string;
  cardBackgroundColor?: string; // Inner card surface (comparison); defaults to theme.surfaceColor
  backgroundImage?: string; // AI-generated or stock image rendered behind the component
  backgroundVideo?: string; // Video clip rendered behind the component (takes priority over backgroundImage)
  backgroundVideoStart?: number; // Seek position in seconds for background video (default 0)
  backgroundOverlay?: number; // Opacity of dark overlay on backgroundImage/backgroundVideo (0-1, default 0.55)
  color?: string;
  accentColor?: string;
  fontSize?: number;
  // Animation & transitions
  animation?: string;
  transition_in?: string;
  transition_out?: string;
  transition_duration?: number;
  transform?: {
    animation?: string;
    scale?: number;
    position?: string | { x: number; y: number };
  };
  // Anime scene props (type: "anime_scene")
  images?: string[];
  particles?: ParticleType;
  particleColor?: string;
  particleCount?: number;
  particleIntensity?: number;
  vignette?: boolean;
  lightingFrom?: string;
  lightingTo?: string;
  // Terminal scene props (type: "terminal_scene")
  steps?: TerminalStep[];
  terminalTitle?: string;
  prompt?: string;
  // Screenshot scene props (type: "screenshot_scene")
  screenshotSteps?: ScreenshotStep[];
  screenshotSize?: { width: number; height: number };
  cursorStartAt?: [number, number];
}

interface Overlay {
  /** emphasis only: seconds the line stays up */
  hold?: number;
  /** emphasis only: "data" sets a bare figure in the mono level */
  level?: string;
  type: "section_title" | "stat_reveal" | "hero_title" | "provider_chip" | "emphasis";
  in_seconds: number;
  out_seconds: number;
  text?: string;
  subtitle?: string;
  accentColor?: string;
  position?: string;
  // provider_chip
  providers?: string[];
  cycleSeconds?: number;
  label?: string;
}

interface AudioLayer {
  src: string;
  volume?: number;
  /** seconds into `src` at which this render begins */
  startFrom?: number;
}

interface AudioConfig {
  narration?: AudioLayer;
  music?: AudioLayer & {
    fadeInSeconds?: number;
    fadeOutSeconds?: number;
    /** Start playback from this offset in seconds (skip quiet intros).
     *  Use the audio_energy tool to find the optimal offset. */
    offsetSeconds?: number;
    /** Loop the music if it's shorter than the video duration. */
    loop?: boolean;
  };
}

export interface ExplainerProps {
  [key: string]: unknown;
  cuts: Cut[];
  overlays?: Overlay[];
  captions?: WordCaption[];
  audio?: AudioConfig;
  /**
   * Caption register. "karaoke" is the stock word-highlight overlay; the
   * documentary playbook uses "documentary" — whole phrases, unhighlighted,
   * over a scrim. See src/design/DocCaption.tsx for why.
   */
  caption_style?: "karaoke" | "documentary";
}

// ---------------------------------------------------------------------------
// Image Extensions
// ---------------------------------------------------------------------------

const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"];
// .ogv/.ogg are common on Wikimedia Commons; without them an Ogg clip
// falls through to the image branch and the render dies on "Error loading
// image". The manifest's own `type` field is not reliable here — several
// video files are recorded as type "image" — so the extension decides.
const VIDEO_EXTENSIONS = [".mp4", ".mov", ".webm", ".avi", ".mkv", ".ogv", ".ogg", ".m4v"];

function isImage(source: string): boolean {
  const lower = source.toLowerCase();
  return IMAGE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function isVideo(source: string): boolean {
  const lower = source.toLowerCase();
  return VIDEO_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

// ---------------------------------------------------------------------------
// Cinematic vignette overlay
// ---------------------------------------------------------------------------

const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.6) 100%)",
      pointerEvents: "none",
    }}
  />
);

// ---------------------------------------------------------------------------
// Enhanced Image Scene — spring physics, parallax, variety
// ---------------------------------------------------------------------------

const ImageScene: React.FC<{ src: string; animation?: string }> = ({
  src,
  animation,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Smooth spring fade-in
  const fadeIn = spring({ frame, fps, config: { damping: 18, stiffness: 80 } });

  // Fade-out for crossfade effect
  const fadeOutStart = durationInFrames - 8;
  const fadeOut = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0.3], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let scale = 1;
  let translateX = 0;
  let translateY = 0;
  const anim = animation || "zoom-in";

  // Progress with easing — smoother than linear
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (anim === "zoom-in") {
    scale = 1 + progress * 0.18;
  } else if (anim === "zoom-out") {
    scale = 1.18 - progress * 0.18;
  } else if (anim === "pan-left") {
    translateX = interpolate(progress, [0, 1], [40, -40]);
    scale = 1.15;
  } else if (anim === "pan-right") {
    translateX = interpolate(progress, [0, 1], [-40, 40]);
    scale = 1.15;
  } else if (anim === "ken-burns" || anim === "ken-burns-slow-zoom") {
    // Cinematic Ken Burns: gentle zoom + diagonal drift
    scale = 1 + progress * 0.22;
    translateX = interpolate(progress, [0, 1], [0, -25]);
    translateY = interpolate(progress, [0, 1], [0, -15]);
  } else if (anim === "parallax") {
    // Subtle parallax — foreground moves faster
    translateY = interpolate(progress, [0, 1], [15, -15]);
    scale = 1.1;
  }
  // "static" or "none" → just display

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#0F172A" }}>
      <Img
        src={resolveAsset(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn * fadeOut,
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
          willChange: "transform, opacity",
        }}
      />
      <Vignette />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Enhanced Video Scene
// ---------------------------------------------------------------------------

const VideoScene: React.FC<{
  src: string;
  startFrom?: number;
  transitionIn?: string;
  transitionOut?: string;
  transitionDuration?: number;
  sceneDurationSeconds: number;
  backgroundColor?: string;
}> = ({
  src,
  startFrom = 0,
  transitionIn,
  transitionOut,
  transitionDuration,
  sceneDurationSeconds,
  backgroundColor = "#0F172A",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const durationInFrames = Math.max(1, Math.round(sceneDurationSeconds * fps));

  const hardIn = ["cut", "none"].includes((transitionIn || "").toLowerCase());
  const hardOut = ["cut", "none"].includes((transitionOut || "").toLowerCase());
  const transitionFrames = Math.max(
    1,
    Math.round((transitionDuration ?? 8 / fps) * fps),
  );
  const fadeIn = hardIn
    ? 1
    : interpolate(frame, [0, transitionFrames], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
  const fadeOutStart = Math.max(0, durationInFrames - transitionFrames);
  const fadeOut = hardOut
    ? 1
    : interpolate(frame, [fadeOutStart, durationInFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  return (
    <AbsoluteFill style={{ background: backgroundColor }}>
      <OffthreadVideo
        src={resolveAsset(src)}
        startFrom={Math.round(startFrom * fps)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn * fadeOut,
        }}
        muted
      />
      <Vignette />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Scene renderer — maps cut type / source to the right component
// ---------------------------------------------------------------------------

// Background image layer — renders an AI-generated/stock image behind data components
const BackgroundImageLayer: React.FC<{
  src: string;
  overlayOpacity?: number;
  children: React.ReactNode;
}> = ({ src, overlayOpacity = 0.55, children }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Subtle ken-burns on the background
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bgScale = 1 + progress * 0.08;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {/* Background image with subtle zoom */}
      <Img
        src={resolveAsset(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${bgScale})`,
          willChange: "transform",
        }}
      />
      {/* Dark overlay for readability */}
      <AbsoluteFill
        style={{
          background: `rgba(15, 23, 42, ${overlayOpacity})`,
        }}
      />
      {/* Component content on top */}
      {children}
    </AbsoluteFill>
  );
};

// Background video layer — plays a looping video behind component content with dark overlay
const BackgroundVideoLayer: React.FC<{
  src: string;
  startFrom?: number;
  overlayOpacity?: number;
  children: React.ReactNode;
}> = ({ src, startFrom = 0, overlayOpacity = 0.55, children }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {/* Background video */}
      <OffthreadVideo
        src={resolveAsset(src)}
        startFrom={Math.round(startFrom * fps)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
        muted
      />
      {/* Dark overlay for readability */}
      <AbsoluteFill
        style={{
          background: `rgba(15, 23, 42, ${overlayOpacity})`,
        }}
      />
      {/* Component content on top */}
      {children}
    </AbsoluteFill>
  );
};

export const SceneRenderer: React.FC<{ cut: Cut; theme: ThemeConfig }> = ({ cut, theme }) => {
  // Wrap component with background video or image if specified
  const maybeWrapWithBg = (element: React.ReactElement) => {
    if (cut.backgroundVideo) {
      return (
        <BackgroundVideoLayer
          src={cut.backgroundVideo}
          startFrom={cut.backgroundVideoStart ?? 0}
          overlayOpacity={cut.backgroundOverlay ?? 0.55}
        >
          {element}
        </BackgroundVideoLayer>
      );
    }
    if (cut.backgroundImage) {
      return (
        <BackgroundImageLayer
          src={cut.backgroundImage}
          overlayOpacity={cut.backgroundOverlay ?? 0.55}
        >
          {element}
        </BackgroundImageLayer>
      );
    }
    return element;
  };

  // Resolve the scene element based on cut type, then wrap with backgroundImage if set
  // Use transparent bg so the animated gradient background shows through
  // When no explicit backgroundColor on the cut, inherit from theme
  const rawBg = (cut.backgroundImage || cut.backgroundVideo) ? "transparent" : (cut.backgroundColor || theme.surfaceColor);
  const bgColor = (rawBg === theme.backgroundColor || rawBg === "#0F172A" || rawBg === "#0f172a") ? "transparent" : rawBg;
  const textColor = cut.color || theme.textColor;
  const accent = cut.accentColor || theme.accentColor;

  // Explicit component types — use theme-derived defaults for colors
  // ── wak3up-documentary components ───────────────────────────────
  // The persistent frame layer. Every documentary scene carries the same
  // dossier furniture, so it is lifted out of the per-type branches.
  const chrome = {
    actNumber: cut.actNumber,
    actTitle: cut.actTitle,
    sceneIndex: cut.sceneIndex,
    coords: cut.coords,
    kicker: cut.kicker,
    source: cut.sourceLine,
  };

  if (cut.type === "annotated_still" && cut.backgroundImage) {
    return (<AnnotatedStill image={cut.backgroundImage} parallax={cut.parallax}
      annotations={cut.annotations} measurement={cut.measurement}
      cutaway={cut.cutaway} caption={cut.caption} title={cut.title} dim={cut.dim} {...chrome} />);
  }
  if (cut.type === "schematic" && cut.layers) {
    return (<Schematic viewBox={cut.viewBox} layers={cut.layers} reveals={cut.reveals}
      labels={cut.labels} title={cut.title} caption={cut.caption} {...chrome} />);
  }
  if (cut.type === "map_route" && cut.route) {
    return (<MapRoute route={cut.route} markers={cut.markers} center={cut.center}
      scale={cut.scale} draw_seconds={cut.draw_seconds} draw_at={cut.draw_at}
      distance_callout={cut.distance_callout} title={cut.title} caption={cut.caption}
      arc={cut.arc} {...chrome} />);
  }
  if (cut.type === "timeline" && cut.events) {
    return (<Timeline events={cut.events} orientation={cut.orientation} span={cut.span}
      playhead={cut.playhead} title={cut.title} caption={cut.caption} {...chrome} />);
  }
  if (cut.type === "document_reveal" && cut.lines) {
    return (<DocumentReveal headline={cut.headline} lines={cut.lines} source={cut.sourceLine}
      image={cut.backgroundImage} paper={cut.paper} light_sweep={cut.light_sweep}
      sweep_at={cut.sweep_at} caption={cut.caption} kicker={cut.kicker}
      actNumber={cut.actNumber} actTitle={cut.actTitle} sceneIndex={cut.sceneIndex}
      coords={cut.coords} />);
  }
  if (cut.type === "act_title_card" && cut.act && cut.title) {
    return (<ActTitleCard act={cut.act} title={cut.title} epigraph={cut.epigraph}
      image={cut.backgroundImage} fade_in={cut.fade_in} fade_out={cut.fade_out} />);
  }
  if (cut.type === "evidence_card" && cut.claim && cut.attribution) {
    return (<EvidenceCard index={cut.index} claim={cut.claim} attribution={cut.attribution}
      detail={cut.detail} status={cut.status} caption={cut.caption}
      actNumber={cut.actNumber} actTitle={cut.actTitle} sceneIndex={cut.sceneIndex}
      source={cut.sourceLine} />);
  }
  if (cut.type === "outro_cta" && cut.title && cut.like_at !== undefined) {
    return (<OutroCta title={cut.title} kicker={cut.kicker}
      like_at={cut.like_at} subscribe_at={cut.subscribe_at ?? cut.like_at + 1}
      subscribe_label={cut.subscribe_label} sceneIndex={cut.sceneIndex}
      actNumber={cut.actNumber} actTitle={cut.actTitle} />);
  }
  if (cut.type === "scale_comparison" && cut.items && cut.unit) {
    return (<ScaleComparison items={cut.items} unit={cut.unit} decimals={cut.decimals}
      title={cut.title} footnote={cut.footnote} caption={cut.caption} at={cut.at}
      actNumber={cut.actNumber} actTitle={cut.actTitle} sceneIndex={cut.sceneIndex}
      kicker={cut.kicker} source={cut.sourceLine} />);
  }
  if (cut.type === "text_card" && cut.text) {
    return maybeWrapWithBg(
      <TextCard text={cut.text} fontSize={cut.fontSize} color={textColor} backgroundColor={bgColor} />
    );
  }
  if (cut.type === "stat_card" && cut.stat) {
    return maybeWrapWithBg(
      <StatCard stat={cut.stat} subtitle={cut.subtitle} accentColor={accent} backgroundColor={bgColor} />
    );
  }
  if (cut.type === "callout" && cut.text) {
    return maybeWrapWithBg(
      <CalloutBox
        text={cut.text} type={cut.callout_type} title={cut.title}
        borderColor={accent} backgroundColor={cut.backgroundColor || theme.surfaceColor}
        textColor={textColor} containerBackgroundColor={bgColor}
      />
    );
  }
  if (cut.type === "comparison" && cut.leftLabel && cut.rightLabel && cut.leftValue && cut.rightValue) {
    return maybeWrapWithBg(
      <ComparisonCard
        leftLabel={cut.leftLabel} rightLabel={cut.rightLabel}
        leftValue={cut.leftValue} rightValue={cut.rightValue}
        title={cut.title} backgroundColor={bgColor} textColor={textColor}
        cardBackgroundColor={cut.cardBackgroundColor || theme.surfaceColor}
      />
    );
  }
  if (cut.type === "hero_title" && cut.text) {
    return maybeWrapWithBg(
      <HeroTitle
        title={cut.text}
        subtitle={cut.heroSubtitle || cut.subtitle}
        accentColor={accent}
        textColor={textColor}
        subtitleColor={theme.mutedTextColor}
        scrimBackground={heroScrim(theme)}
      />
    );
  }
  if (cut.type === "terminal_scene" && cut.steps) {
    return maybeWrapWithBg(
      <TerminalScene
        title={cut.terminalTitle || "Terminal"}
        steps={cut.steps as TerminalStep[]}
        prompt={cut.prompt}
        accentColor={accent}
        backgroundColor={bgColor || theme.backgroundColor}
      />
    );
  }
  if (cut.type === "screenshot_scene" && cut.backgroundImage && cut.screenshotSteps) {
    return (
      <ScreenshotScene
        backgroundImage={cut.backgroundImage}
        backgroundSize={cut.screenshotSize}
        steps={cut.screenshotSteps as ScreenshotStep[]}
        accentColor={accent}
        cursorStartAt={cut.cursorStartAt}
      />
    );
  }

  // --- Chart types — use theme.chartColors as default palette ---
  if (cut.type === "bar_chart" && cut.chartData) {
    return maybeWrapWithBg(
      <BarChart
        data={cut.chartData} title={cut.title} colors={cut.chartColors || theme.chartColors}
        animationStyle={(cut.chartAnimation as any) || "grow-up"}
        showGrid={cut.showGrid} showValues={cut.showValues} backgroundColor={bgColor}
        textColor={textColor}
      />
    );
  }
  if (cut.type === "line_chart" && cut.chartSeries) {
    return maybeWrapWithBg(
      <LineChart
        series={cut.chartSeries} title={cut.title} colors={cut.chartColors || theme.chartColors}
        animationStyle={(cut.chartAnimation as any) || "draw"}
        showGrid={cut.showGrid} showMarkers={cut.showMarkers} showLegend={cut.showLegend}
        xLabel={cut.xLabel} yLabel={cut.yLabel} backgroundColor={bgColor}
        textColor={textColor}
      />
    );
  }
  if (cut.type === "pie_chart" && cut.chartData) {
    return maybeWrapWithBg(
      <PieChart
        data={cut.chartData} title={cut.title} colors={cut.chartColors || theme.chartColors}
        animationStyle={(cut.chartAnimation as any) || "expand"}
        donut={cut.donut} centerLabel={cut.centerLabel} centerValue={cut.centerValue}
        showLegend={cut.showLegend} backgroundColor={bgColor}
        textColor={textColor}
      />
    );
  }
  if (cut.type === "kpi_grid" && cut.chartData) {
    return maybeWrapWithBg(
      <KPIGrid
        metrics={cut.chartData} title={cut.title} columns={cut.columns}
        colors={cut.chartColors || theme.chartColors} animationStyle={(cut.chartAnimation as any) || "count-up"}
        backgroundColor={bgColor}
        textColor={textColor}
      />
    );
  }
  if (cut.type === "progress_bar" && cut.progress !== undefined) {
    return maybeWrapWithBg(
      <AbsoluteFill
        style={{
          background: bgColor || theme.surfaceColor,
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: "80px 120px",
        }}
      >
        {cut.title && (
          <div style={{
            position: "absolute", top: 120, fontSize: 48, fontWeight: 700,
            color: textColor, textAlign: "center", width: "100%",
          }}>
            {cut.title}
          </div>
        )}
        <ProgressBar
          progress={cut.progress} label={cut.progressLabel}
          color={cut.progressColor || accent}
          animationStyle={(cut.progressAnimation as any) || "fill"}
          segments={cut.progressSegments} backgroundColor={cut.backgroundColor || theme.surfaceColor}
        />
      </AbsoluteFill>
    );
  }

  // --- Anime scene (multi-image crossfade + particles) ---
  if (cut.type === "anime_scene" && cut.images && cut.images.length > 0) {
    return (
      <AnimeScene
        images={cut.images}
        animation={(cut.animation as CameraMotion) || "ken-burns"}
        particles={cut.particles}
        particleColor={cut.particleColor}
        particleCount={cut.particleCount}
        particleIntensity={cut.particleIntensity}
        backgroundColor={cut.backgroundColor}
        vignette={cut.vignette ?? true}
        lightingFrom={cut.lightingFrom}
        lightingTo={cut.lightingTo}
        sceneDurationSeconds={cut.out_seconds - cut.in_seconds}
      />
    );
  }

  // --- Media types (image / video fallback) ---
  const animation = cut.animation || cut.transform?.animation;

  /**
   * Sourced photography and footage get the same treatment as the authored
   * scenes: the film's grade, and the persistent frame.
   *
   * Without this the cuts announce themselves — a raw blue-sky JPEG next to a
   * graded schematic is the clearest tell of a documentary assembled from
   * stock, which is exactly what the compose director warns about. The frame
   * is applied when the cut carries act chrome, so other pipelines using this
   * composition are untouched.
   */
  const inDocumentary = Boolean(cut.actNumber || cut.actTitle);
  const dress = (el: React.ReactElement): React.ReactElement =>
    inDocumentary ? (
      <AbsoluteFill>
        <Graded>{el}</Graded>
        <FrameLayer
          actNumber={cut.actNumber}
          actTitle={cut.actTitle}
          sceneIndex={cut.sceneIndex}
          coords={cut.coords}
        />
        <SourceCaption caption={cut.caption} source={cut.sourceLine} />
      </AbsoluteFill>
    ) : (
      el
    );

  if (cut.source && isImage(cut.source)) {
    return maybeWrapWithBg(dress(<ImageScene src={cut.source} animation={animation} />));
  }

  if (cut.source && isVideo(cut.source)) {
    return maybeWrapWithBg(
      dress(
        <VideoScene
          src={cut.source}
          startFrom={cut.source_in_seconds ?? 0}
          transitionIn={cut.transition_in}
          transitionOut={cut.transition_out}
          transitionDuration={cut.transition_duration}
          sceneDurationSeconds={cut.out_seconds - cut.in_seconds}
          backgroundColor={cut.backgroundColor}
        />,
      ),
    );
  }

  // Final fallback — try as image if source exists, otherwise show text_card
  if (cut.source) {
    return maybeWrapWithBg(dress(<ImageScene src={cut.source} animation={animation} />));
  }

  // No source, no type — render as text card with cut id as fallback
  return <TextCard text={cut.text || cut.id} color={textColor} backgroundColor={bgColor} />;
};

// ---------------------------------------------------------------------------
// Overlay renderer
// ---------------------------------------------------------------------------

const OverlayRenderer: React.FC<{ overlay: Overlay; theme: ThemeConfig }> = ({
  overlay,
  theme,
}) => {
  // The documentary's own emphasis beat — a narration line held over the
  // picture in Display. Stock section_title is a themed lower third and reads
  // as a different film.
  if (overlay.type === "emphasis") {
    return (
      <EmphasisLine
        text={overlay.text ?? ""}
        hold={overlay.hold as number | undefined}
        level={(overlay.level as "display" | "data") ?? "display"}
      />
    );
  }
  if (overlay.type === "section_title") {
    return (
      <SectionTitle
        title={overlay.text ?? ""}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor || theme.accentColor}
        textColor={theme.textColor}
        position={(overlay.position as any) || "top-left"}
      />
    );
  }
  if (overlay.type === "stat_reveal") {
    return (
      <StatReveal
        stat={overlay.text ?? ""}
        label={overlay.subtitle}
        accentColor={overlay.accentColor || theme.accentColor}
        textColor={theme.textColor}
        position={(overlay.position as any) || "bottom-right"}
      />
    );
  }
  if (overlay.type === "hero_title") {
    return (
      <HeroTitle
        title={overlay.text ?? ""}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor || theme.accentColor}
        textColor={theme.textColor}
        subtitleColor={theme.mutedTextColor}
        scrimBackground={heroScrim(theme)}
      />
    );
  }
  if (overlay.type === "provider_chip" && overlay.providers) {
    return (
      <ProviderChip
        providers={overlay.providers as string[]}
        cycleSeconds={overlay.cycleSeconds}
        position={(overlay.position as any) || "bottom-right"}
        accentColor={overlay.accentColor}
        label={overlay.label}
      />
    );
  }
  return null;
};

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------

export const Explainer: React.FC<ExplainerProps> = (props) => {
  const { cuts, overlays, captions, audio } = props;
  const captionStyle = props.caption_style ?? "karaoke";
  const { fps, durationInFrames } = useVideoConfig();

  // Resolve theme from props — playbook name, theme name, or custom themeConfig
  const theme = resolveTheme(props as Record<string, unknown>);

  return (
    <AbsoluteFill style={{ background: theme.backgroundColor, fontFamily: theme.headingFont || fontFamily }}>
      {/* Layer 0: Animated gradient background — driven by theme */}
      <AnimatedBackground theme={theme} />

      {/* Layer 1: Visual scenes */}
      {cuts.map((cut) => {
        const from = Math.round(cut.in_seconds * fps);
        const duration = Math.round((cut.out_seconds - cut.in_seconds) * fps);

        return (
          <Sequence key={cut.id} from={from} durationInFrames={duration}>
            <SceneRenderer cut={cut} theme={theme} />
          </Sequence>
        );
      })}

      {/* Layer 2: Overlays (section titles, stat reveals, hero titles) */}
      {overlays?.map((overlay, i) => {
        const from = Math.round(overlay.in_seconds * fps);
        const duration = Math.round(
          (overlay.out_seconds - overlay.in_seconds) * fps
        );

        return (
          <Sequence key={`overlay-${i}`} from={from} durationInFrames={duration}>
            <OverlayRenderer overlay={overlay} theme={theme} />
          </Sequence>
        );
      })}

      {/* Layer 3: Captions (word-by-word highlight) */}
      {captions && captions.length > 0 && captionStyle === "documentary" && (
        <DocCaption words={captions} />
      )}
      {captions && captions.length > 0 && captionStyle !== "documentary" && (
        <CaptionOverlay
          words={captions}
          wordsPerPage={6}
          fontSize={42}
          color={theme.textColor}
          highlightColor={theme.captionHighlightColor}
          backgroundColor={theme.captionBackgroundColor}
        />
      )}

      {/* Layer 4: Audio — narration */}
      {audio?.narration?.src && (
        <Audio
          src={resolveAsset(audio.narration.src)}
          // Offset into a longer mix. A film rendered in act-sized parts needs
          // each part to start at its own point in the single finished mix
          // rather than carrying six separately normalised files.
          startFrom={Math.round((audio.narration.startFrom ?? 0) * fps)}
          volume={audio.narration.volume ?? 1}
        />
      )}

      {/* Layer 4: Audio — music with offset, fade in/out, and optional loop */}
      {audio?.music?.src && (
        <Audio
          src={resolveAsset(audio.music.src)}
          startFrom={Math.round((audio.music.offsetSeconds ?? 0) * fps)}
          loop={audio.music.loop ?? false}
          loopVolumeCurveBehavior="repeat"
          volume={(f) => {
            const baseVol = audio.music!.volume ?? 0.1;
            const fadeInDur = (audio.music!.fadeInSeconds ?? 2) * fps;
            const fadeOutDur = (audio.music!.fadeOutSeconds ?? 3) * fps;
            const totalFrames = durationInFrames;

            // Fade in
            const fadeIn = interpolate(f, [0, fadeInDur], [0, baseVol], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            // Fade out
            const fadeOut = interpolate(
              f,
              [totalFrames - fadeOutDur, totalFrames],
              [baseVol, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return Math.min(fadeIn, fadeOut);
          }}
        />
      )}
    </AbsoluteFill>
  );
};
