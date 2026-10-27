import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { SYS, TYPE, TRACK, EXPO_OUT, LAYOUT, stagger } from "../design/system";
import { SceneShell } from "../design/Scene";
import { TextureName } from "../design/Texture";
import { T } from "../design/Type";
import { TYPE_CLASS } from "../design/layers";

export type EvidenceStatus = "peer_reviewed" | "contested" | "unpublished" | "measured" | "claim";

const STATUS_LABEL: Record<EvidenceStatus, string> = {
  peer_reviewed: "peer reviewed",
  contested: "contested",
  unpublished: "not published",
  measured: "measured",
  claim: "claim",
};

export interface EvidenceCardProps {
  /**
   * House-library texture behind the scene. Omit for the default; pass
   * `null` to go back to the flat ground. See `design/Texture.tsx`.
   */
  texture?: TextureName | null;

  /** ledger id or running index — the dossier's own numbering */
  index?: string;
  /** the claim, stated once, in the Display level */
  claim: string;
  /** who says so: author, journal, year — exactly as the ledger records it */
  attribution: string;
  /** optional second line: the method or the sample */
  detail?: string;
  status?: EvidenceStatus;
  /** the frame's data strip */
  actNumber?: string;
  actTitle?: string;
  sceneIndex?: string;
  caption?: string;
  source?: string;
}

/**
 * The citation beat. The film repeatedly has to show *who established a thing*
 * rather than the thing itself, and a photograph cannot do that. This is the
 * card for it: a claim, its attribution, and an honest status chip — the chip
 * is what keeps a contested claim from reading like a settled one.
 */
export const EvidenceCard: React.FC<EvidenceCardProps> = ({
  texture,
  index,
  claim,
  attribution,
  detail,
  status = "peer_reviewed",
  actNumber,
  actTitle,
  sceneIndex,
  caption,
  source,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const boxStart = 0.2 * fps;
  const boxP = interpolate(frame, [boxStart, boxStart + SYS.move], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  const chipStart = 1.5 * fps;
  const chipP = interpolate(frame, [chipStart, chipStart + SYS.unit], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EXPO_OUT),
  });

  const contested = status === "contested" || status === "unpublished";

  /*
   * ON PAPER THE CARD'S OWN TYPE HAS TO INVERT TOO, not just the chrome.
   * `paperInk` flips the frame furniture -- hairline, data strip, caption --
   * and leaves the card body alone, so the first textured render put the
   * claim in off-white on off-white parchment and it could not be read at
   * all. The claim is the one thing on this card that must survive.
   */
  const onPaper = texture !== null;
  const ink = onPaper
    ? { text: SYS.paperInk, muted: "rgba(36,31,24,0.62)", accent: "#8A5A1E" }
    : { text: SYS.text, muted: SYS.muted, accent: SYS.accent };
  const chipColor = contested ? ink.muted : ink.accent;

  return (
    <SceneShell
      {...(texture === null
        ? {}
        : { texture: texture ?? "parchment", textureKind: "paper" as const,
            paperInk: true })}
      actNumber={actNumber}
      actTitle={actTitle}
      sceneIndex={sceneIndex}
      caption={caption}
      source={source}
      sweepAt={0.35}
    >
      <div
        style={{
          position: "absolute",
          left: LAYOUT.left + 48,
          right: LAYOUT.left + 48,
          top: "50%",
          transform: "translateY(-50%)",
          display: "flex",
          gap: 54,
          alignItems: "flex-start",
        }}
      >
        {/* left rail: the ledger number, vertically ruled */}
        <div style={{ width: 150, flexShrink: 0, textAlign: "right", paddingTop: 10 }}>
          {index ? (
            <T level="data" size={TYPE.data} color={ink.accent} at={0.1} align="right">
              {index}
            </T>
          ) : null}
          <div
            style={{
              marginTop: 18,
              marginLeft: "auto",
              width: 1,
              height: 96 * boxP,
              background: onPaper ? "rgba(36,31,24,0.30)" : SYS.rule,
            }}
          />
        </div>

        <div style={{ flex: 1, maxWidth: 1180 }}>
          {/* The claim passed NO colour, so it took `T`'s default — which is
              the film's off-white, and on parchment that is off-white on
              off-white. The one line on this card that must be readable was
              the one line not told what colour to be. */}
          <T level="display" size={TYPE.display} color={ink.text} at={0.35}
             index={0} style={{ lineHeight: 1.18 }}>
            {claim}
          </T>

          <div
            style={{
              marginTop: 34,
              width: `${100 * boxP}%`,
              height: 1,
              background: onPaper ? "rgba(36,31,24,0.30)" : SYS.rule,
            }}
          />

          <T
            level="data"
            size={TYPE.dataSm}
            color={ink.text}
            at={1.1}
            index={0}
            style={{ marginTop: 24, letterSpacing: "0.06em" }}
          >
            {attribution}
          </T>

          {detail ? (
            <T
              level="body"
              size={TYPE.bodySm}
              color={ink.muted}
              at={1.1}
              index={1}
              style={{ marginTop: 10 }}
            >
              {detail}
            </T>
          ) : null}

          <div
            style={{
              marginTop: 30,
              opacity: chipP,
              transform: `translateZ(0) translateY(${Math.round((1 - chipP) * SYS.rise)}px)`,
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              border: `1px solid ${chipColor}`,
              borderLeft: `3px solid ${chipColor}`,
              padding: "9px 18px",
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                background: chipColor,
                borderRadius: contested ? 0 : 999,
                display: "inline-block",
              }}
            />
            <span className={TYPE_CLASS}
              style={{
                fontFamily: SYS.label,
                fontSize: TYPE.labelSm - 3,
                letterSpacing: TRACK,
                textTransform: "uppercase",
                color: chipColor,
                fontWeight: 500,
              }}
            >
              {STATUS_LABEL[status]}
            </span>
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
