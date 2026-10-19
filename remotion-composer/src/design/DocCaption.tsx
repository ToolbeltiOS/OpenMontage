import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, EXPO_OUT, LAYOUT } from "./system";
import type { WordCaption } from "../components/CaptionOverlay";

export interface DocCaptionProps {
  words: WordCaption[];
  /** words per page; documentary subtitles read in phrases, not single words */
  wordsPerPage?: number;
  fontSize?: number;
  /** lift the block clear of the bottom chrome */
  bottom?: number;
  maxWidth?: number;
}

interface Page {
  text: string;
  startMs: number;
  endMs: number;
}

/**
 * Narration subtitles in the documentary register.
 *
 * The stock CaptionOverlay is a karaoke highlighter — one word lit at a time,
 * bold, in a coloured box. That is the wrong instrument here: it pulls the eye
 * off the photograph and reads as social video. This renders whole phrases,
 * unhighlighted, in the Body level, over a soft scrim rather than a plate, and
 * cross-fades between pages on the system's micro duration so nothing snaps.
 *
 * Pages break on `pageBreakAfter` first — the synthesis is per-sentence, so
 * those breaks are real sentence boundaries — and only then on word count.
 */
export const DocCaption: React.FC<DocCaptionProps> = ({
  words,
  wordsPerPage = 9,
  fontSize = TYPE.body + 10,
  bottom = LAYOUT.bottom + 128,
  maxWidth = 1360,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;

  const pages = useMemo<Page[]>(() => {
    const out: Page[] = [];
    let buf: WordCaption[] = [];
    const flush = () => {
      if (!buf.length) return;
      out.push({
        text: buf.map((w) => w.word).join(" "),
        startMs: buf[0].startMs,
        endMs: buf[buf.length - 1].endMs,
      });
      buf = [];
    };
    for (const w of words) {
      buf.push(w);
      if (w.pageBreakAfter || buf.length >= wordsPerPage) flush();
    }
    flush();
    return out;
  }, [words, wordsPerPage]);

  // a page stays up until the next one starts, so there is no flicker in a gap
  const idx = pages.findIndex((p, i) => {
    const next = pages[i + 1];
    return ms >= p.startMs - 120 && (next ? ms < next.startMs - 120 : ms <= p.endMs + 700);
  });
  if (idx < 0) return null;

  const page = pages[idx];
  const fadeMs = (SYS.micro / fps) * 1000;
  const o = Math.min(
    interpolate(ms, [page.startMs - 120, page.startMs - 120 + fadeMs], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(...EXPO_OUT),
    }),
    1,
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* scrim, not a box: a gradient that only exists where the text is */}
      <AbsoluteFill
        style={{
          // the scrim exists only where the type is, and is strong enough to
          // hold a 34px line over sunlit stone
          background: `linear-gradient(0deg, rgba(12,12,14,0.82) 0%, rgba(12,12,14,0.62) ${Math.round(
            (bottom + 120) / 10.8,
          )}%, transparent ${Math.round((bottom + 300) / 10.8)}%)`,
          opacity: o,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom,
          display: "flex",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            maxWidth,
            textAlign: "center",
            fontFamily: SYS.body,
            fontWeight: 400,
            fontSize,
            lineHeight: 1.36,
            color: SYS.text,
            letterSpacing: "0.005em",
            opacity: o,
            transform: `translateY(${(1 - o) * (SYS.rise / 2)}px)`,
            textShadow: "0 1px 14px rgba(0,0,0,0.75), 0 0 2px rgba(0,0,0,0.9)",
            textWrap: "balance" as React.CSSProperties["textWrap"],
          }}
        >
          {page.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
