import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { SYS, TYPE, TRACK, SHADOW } from "../design/system";
import { Graded } from "../design/Frame";

export interface ThumbnailProps {
  [key: string]: unknown;
  /** the photograph, as a path under remotion-composer/public/ */
  image: string;
  /** the film's title, set in Display */
  title: string;
  /** a short line above the title; omit for none */
  kicker?: string;
  /** 0-1, where in the frame the subject is, so the type lands clear of it */
  titleSide?: "left" | "right";
  /** push in on the photograph; 1 is the whole frame */
  scale?: number;
  /** -0.5..0.5 of the frame width, to re-centre the crop */
  offsetX?: number;
  offsetY?: number;
}

/**
 * A thumbnail: the picture, the film's grade, and the title. Nothing else.
 *
 * NOT `SlotPreview` with chrome switched off. A thumbnail is a different
 * object from a frame of the film: it carries no act number, no scene index,
 * no source line and no caption, because none of those mean anything outside
 * the film, and at 320px wide on a phone they are illegible noise competing
 * with the only two things that have to read — the picture and the title.
 *
 * It takes the BASE grade, not an act's. An act grade is a relative move
 * inside a film a viewer is already watching; a thumbnail is seen cold and
 * alone, so it gets the film's own look rather than one act's inflection.
 */
export const Thumbnail: React.FC<ThumbnailProps> = ({
  image,
  title,
  kicker,
  titleSide = "left",
  scale = 1.0,
  offsetX = 0,
  offsetY = 0,
}) => (
  <AbsoluteFill style={{ backgroundColor: "#0C0C0E" }}>
    <AbsoluteFill
      style={{
        transform: `scale(${scale}) translate(${offsetX * 100}%, ${offsetY * 100}%)`,
      }}
    >
      {/* Graded with no act, which is BASE_ACT_GRADE by definition. */}
      <Graded>
        <Img
          src={image.startsWith("/") ? image : staticFile(image)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </Graded>
    </AbsoluteFill>

    {/* A scrim under the type only. A full-frame scrim mutes the picture,
        which is the half of a thumbnail that survives being small. */}
    <AbsoluteFill
      style={{
        background:
          titleSide === "left"
            ? "linear-gradient(100deg, rgba(8,8,10,0.86) 0%, rgba(8,8,10,0.72) 38%, rgba(8,8,10,0) 68%)"
            : "linear-gradient(260deg, rgba(8,8,10,0.86) 0%, rgba(8,8,10,0.72) 38%, rgba(8,8,10,0) 68%)",
      }}
    />

    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: titleSide === "left" ? "flex-start" : "flex-end",
        padding: "0 86px",
        textAlign: titleSide === "left" ? "left" : "right",
      }}
    >
      {kicker ? (
        <div
          style={{
            fontFamily: SYS.label,
            fontSize: TYPE.label,
            letterSpacing: TRACK,
            textTransform: "uppercase",
            color: SYS.accent,
            marginBottom: 22,
            textShadow: SHADOW,
          }}
        >
          {kicker}
        </div>
      ) : null}
      <div
        style={{
          fontFamily: SYS.display,
          fontWeight: 600,
          fontSize: TYPE.displayXL,
          lineHeight: 1.04,
          letterSpacing: "-0.015em",
          color: SYS.text,
          maxWidth: "62%",
          textShadow: SHADOW,
        }}
      >
        {title}
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);
