/**
 * OutroCta — reusable end card for Wak3upSociety documentaries.
 *
 * Drop into remotion-composer/src/components/, register in src/schemas/docComponents.ts
 * (schema exported below) and in component-contract.json as "outro_cta".
 *
 * Timing is narration-driven: pass likeAt / subscribeAt (seconds into THIS scene) taken
 * from the word-level captions. Nothing of ours is drawn inside the reserved End Screen
 * zone — the right END_SCREEN_RESERVE of the width and the bottom 20% — because YouTube
 * draws its own elements there and covers whatever is underneath.
 *
 * Uses the design system tokens from ../design/system (palette, type, easing). If your
 * FrameLayer component exposes different prop names, adjust the one usage below.
 */
import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  staticFile,
} from "remotion";
import { z } from "zod";

// ---- adjust these two imports to your tree -----------------------------------------
import { tokens } from "../design/system"; // { color: {bg, ink, accent, accentInk}, font: {display,label,data} }
import { FrameLayer } from "../design/FrameLayer"; // hairline frame + corner ticks + grain + vignette + data strip
// ------------------------------------------------------------------------------------

export const outroCtaSchema = z.object({
  channel: z.string().default("WAK3UPSOCIETY"),
  filmTitle: z.string().default(""), // top-left data strip; the film's title in caps. Empty hides it.
  eyebrow: z.string().default("THANK YOU FOR WATCHING"),
  line1: z.string().default("A like and a subscribe helps us"),
  line2: z.string().default("create more videos like this."),
  scheduleLine: z.string().default("NEW VIDEO EVERY MONDAY"),
  backgroundSrc: z.string().optional(), // dimmed hero still (staticFile path or URL)
  likeAt: z.number().default(3.4), // seconds into this scene when the narrator says "like"
  subscribeAt: z.number().default(5.6), // seconds when the narrator says "subscribe"
  fadeOutSeconds: z.number().default(0.5),
});
export type OutroCtaProps = z.infer<typeof outroCtaSchema>;

// ---- easing (mirror of the design system; expo family only) -------------------------
const expoOut = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));
const expoInOut = (t: number) =>
  t <= 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2;
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

/**
 * Share of the frame width kept clear on the right for YouTube End Screen elements.
 * Widened from a third to 0.40 on 2026-10-20: at a third, the element grid still
 * clipped the end of the headline on a 16:9 player. Stated once here and used to
 * derive the content limit, so the two cannot drift apart.
 */
const END_SCREEN_RESERVE = 0.40;
const CONTENT_LEFT = 200;
/**
 * The headline column runs from CONTENT_LEFT to the reserve boundary — 952px on a
 * 1920 canvas. The brief asked for 900; at 900, line 1 of the approved copy
 * ("A like and a subscribe helps us") wraps and leaves "us" alone on its own line,
 * measured at 62px Display. Running to the boundary keeps both of the other two
 * figures — the 40% reserve and the 62px Display — and the line ends at x=1100,
 * still 52px clear of the reserve.
 */
const seg = (t: number, a: number, b: number, e = expoOut) => e(clamp((t - a) / (b - a), 0, 1));

const textIn = (t: number, at: number): React.CSSProperties => {
  const p = seg(t, at, at + 0.33);
  return { opacity: p, filter: `blur(${(1 - p) * 6}px)`, transform: `translateY(${(1 - p) * 8}px)` };
};

const press = (t: number, at: number) => {
  const d = seg(t, at, at + 0.12, expoInOut);
  const u = seg(t, at + 0.12, at + 0.42);
  return { scale: 1 - 0.08 * d + 0.08 * u, fill: seg(t, at + 0.08, at + 0.35), ring: seg(t, at + 0.1, at + 0.9) };
};

export const OutroCta: React.FC<OutroCtaProps> = (props) => {
  const p = outroCtaSchema.parse(props);
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();
  // The right edge content may not cross. 1920 * 0.60 = 1152, and the headline
  // column ends at 1100.
  const contentLimit = width * (1 - END_SCREEN_RESERVE);
  const t = frame / fps;
  const dur = durationInFrames / fps;

  const C = tokens.color; // bg #0C0C0E, ink #EDE6D8, accent #C08A3E, accentInk #14100A
  const F = tokens.font;

  const fade = 1 - seg(t, 0, 0.5) + seg(t, dur - p.fadeOutSeconds, dur);

  // icons: draw-on then press
  const likeDraw = seg(t, p.likeAt - 1.2, p.likeAt - 0.4);
  const L = press(t, p.likeAt);
  const subDraw = seg(t, p.subscribeAt - 1.2, p.subscribeAt - 0.4);
  const subTextIn = seg(t, p.subscribeAt - 0.8, p.subscribeAt - 0.4);
  const S = press(t, p.subscribeAt);
  const sweepX = -200 + 760 * seg(t, p.subscribeAt + 0.3, p.subscribeAt + 1.0, expoInOut);

  const bellStart = p.subscribeAt + 1.0;
  const bellDraw = seg(t, bellStart, bellStart + 0.7);
  const ring = clamp((t - (bellStart + 0.8)) / 1.0, 0, 1);
  const bellAngle = ring < 1 ? Math.sin(ring * Math.PI * 4) * 12 * (1 - ring) : 0;
  const arcs = ring > 0 && ring < 0.9 ? (0.5 + 0.5 * Math.abs(Math.sin(ring * Math.PI * 4))) * (1 - ring) : 0;

  const nextAt = bellStart + 1.2;

  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {p.backgroundSrc && (
        <Img
          src={p.backgroundSrc.startsWith("http") ? p.backgroundSrc : staticFile(p.backgroundSrc)}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.38, filter: "saturate(0.8)" }}
        />
      )}
      <AbsoluteFill style={{ background: "radial-gradient(70% 70% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,.62) 100%)" }} />

      {/* headline block — left two-thirds */}
      <div
        style={{
          position: "absolute",
          left: CONTENT_LEFT,
          top: 300,
          // Derived, so a narrower canvas wraps the headline inside the column
          // rather than pushing it into the reserved zone.
          width: contentLimit - CONTENT_LEFT,
        }}
      >
        <div style={{ ...textIn(t, 0.6), fontFamily: F.label, fontWeight: 500, fontSize: 26, letterSpacing: 7, color: C.ink, opacity: 0.62 * (textIn(t, 0.6).opacity as number) }}>
          {p.eyebrow}
        </div>
        <div style={{ ...textIn(t, 0.7), fontFamily: F.display, fontWeight: 400, fontSize: 62, lineHeight: 1.15, color: C.ink, marginTop: 22 }}>{p.line1}</div>
        <div style={{ ...textIn(t, 0.8), fontFamily: F.display, fontWeight: 400, fontSize: 62, lineHeight: 1.15, color: C.ink }}>{p.line2}</div>
      </div>

      {/* LIKE */}
      <svg style={{ position: "absolute", left: CONTENT_LEFT, top: 640 }} width={104} height={160} viewBox="0 0 104 160">
        <g transform={`translate(52 52) scale(${L.scale}) translate(-52 -52)`}>
          <circle cx={52} cy={52} r={52 + 40 * L.ring} fill="none" stroke={C.accent} strokeWidth={2} opacity={L.ring > 0 ? (1 - L.ring) * 0.9 : 0} />
          <path
            d="M30 46 h18 l6 -28 a8 8 0 0 1 16 2 v26 h26 a10 10 0 0 1 10 12 l-8 36 a12 12 0 0 1 -12 10 h-38 z M20 46 h10 v58 h-10 z"
            fill={C.accent}
            fillOpacity={L.fill}
            stroke={L.fill > 0.6 ? C.accent : C.ink}
            strokeWidth={3.5}
            strokeLinejoin="round"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - likeDraw}
          />
        </g>
        <text x={52} y={150} textAnchor="middle" fontFamily={F.label} fontWeight={500} fontSize={22} letterSpacing={6} fill={C.ink} fillOpacity={0.7 * (textIn(t, p.likeAt - 0.4).opacity as number)}>
          LIKE
        </text>
      </svg>

      {/* SUBSCRIBE */}
      <svg style={{ position: "absolute", left: CONTENT_LEFT + 160, top: 640 }} width={420} height={160} viewBox="-30 -30 420 160">
        <defs>
          <linearGradient id="outroSweep" x1="0" x2="1">
            <stop offset="0" stopColor="#fff" stopOpacity="0" />
            <stop offset=".5" stopColor="#fff" stopOpacity=".16" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <clipPath id="outroPillClip"><rect x={0} y={0} width={360} height={104} rx={52} /></clipPath>
        </defs>
        <g transform={`translate(180 52) scale(${S.scale}) translate(-180 -52)`}>
          <rect x={-6 - 28 * S.ring} y={-6 - 28 * S.ring} width={372 + 56 * S.ring} height={116 + 56 * S.ring} rx={58 + 28 * S.ring} fill="none" stroke={C.accent} strokeWidth={2} opacity={S.ring > 0 ? (1 - S.ring) * 0.9 : 0} />
          <rect x={0} y={0} width={360} height={104} rx={52} fill={C.accent} fillOpacity={S.fill} stroke={C.ink} strokeWidth={3} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - subDraw} />
          <text x={180} y={62} textAnchor="middle" fontFamily={F.label} fontWeight={600} fontSize={30} letterSpacing={8} fill={S.fill > 0.5 ? C.accentInk : C.ink} opacity={subTextIn}>
            SUBSCRIBE
          </text>
          <g clipPath="url(#outroPillClip)">
            <rect x={sweepX} y={0} width={200} height={104} fill="url(#outroSweep)" opacity={S.fill > 0.9 ? 1 : 0} />
          </g>
        </g>
      </svg>

      {/* BELL */}
      <svg style={{ position: "absolute", left: CONTENT_LEFT + 590, top: 640 }} width={80} height={110} viewBox="0 0 80 110">
        <g transform={`translate(40 12) rotate(${bellAngle}) translate(-40 -12)`}>
          <path
            d="M40 14 v8 M24 70 a16 16 0 0 0 32 0 M40 22 c-16 0 -24 12 -24 28 v16 l-8 10 h64 l-8 -10 v-16 c0 -16 -8 -28 -24 -28 z M34 92 a6 6 0 0 0 12 0"
            fill="none"
            stroke={ring > 0 ? C.accent : C.ink}
            strokeWidth={3.5}
            strokeLinejoin="round"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - bellDraw}
          />
        </g>
        <path d="M6 36 a40 40 0 0 1 10 -22" fill="none" stroke={C.accent} strokeWidth={3} strokeLinecap="round" opacity={arcs} />
        <path d="M74 36 a40 40 0 0 0 -10 -22" fill="none" stroke={C.accent} strokeWidth={3} strokeLinecap="round" opacity={arcs} />
      </svg>

      {/* schedule line — unchanged; already above the bottom 20% End Screen zone */}
      <div style={{ position: "absolute", left: CONTENT_LEFT, top: 820, display: "flex", alignItems: "center", gap: 20, ...textIn(t, nextAt) }}>
        <span style={{ width: 52, height: 2, background: C.accent }} />
        <span style={{ fontFamily: F.label, fontWeight: 500, fontSize: 24, letterSpacing: 6, color: C.ink, opacity: 0.8 }}>{p.scheduleLine}</span>
      </div>

      {/* frame layer: hairline, ticks, grain, vignette, data strip */}
      <FrameLayer topLeft={p.filmTitle.toUpperCase()} bottomRight={p.channel} channelPosition="top-right" grain={0.055} vignette={0} lightLeak={false} />

      <AbsoluteFill style={{ background: "#000", opacity: fade, pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};

export default OutroCta;
