import React from 'react';
import { AbsoluteFill } from 'remotion';
import type { Params, SideProps, TransitionImpl } from './types';

export type LayerProps<P extends Params> = {
  /** "in": the layer grows over scene A. "out": the layer leaves to show scene B. */
  phase: 'in' | 'out';
  /** 0..1 within the phase. At phase "in" 1 and phase "out" 0 the frame must be fully covered. */
  progress: number;
  params: P;
};

/**
 * Builds a bridged transition (cover → hold → reveal) from one layer component.
 * The swap from A to B happens while the layer fully covers the frame, so the cut is never seen.
 * `hold` is the share of the transition spent fully covered (0 = swap at the peak).
 */
export const bridged = <P extends Params & { hold?: number }>(
  defaults: P,
  Layer: React.FC<LayerProps<P>>,
): TransitionImpl<P> => {
  const split = (p: number, hold: number) => {
    const inEnd = 0.5 - hold / 2;
    const outStart = 0.5 + hold / 2;
    return { inEnd, outStart };
  };
  const Exiting: React.FC<SideProps<P>> = ({ progress, children, params }) => {
    const { inEnd } = split(progress, params.hold ?? 0.1);
    return (
      <AbsoluteFill>
        {children}
        <Layer phase="in" progress={Math.min(1, progress / inEnd)} params={params} />
      </AbsoluteFill>
    );
  };
  const Entering: React.FC<SideProps<P>> = ({ progress, children, params }) => {
    const { inEnd, outStart } = split(progress, params.hold ?? 0.1);
    if (progress < inEnd) return null;
    return (
      <AbsoluteFill>
        {children}
        <Layer phase="out" progress={Math.max(0, (progress - outStart) / (1 - outStart))} params={params} />
      </AbsoluteFill>
    );
  };
  return { defaults, Exiting, Entering };
};

/** Shows children unchanged. */
// VENDORED EDIT (2026-10-20): upstream types this as FC<SideProps<Params>>,
// which this repo's stricter tsconfig refuses to assign to a transition's
// FC<SideProps<P>> — Params has none of P's own keys. Widening the parameter
// to `any` keeps Pass usable from every transition without changing what it
// does, which is render its children and nothing else.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const Pass: React.FC<SideProps<any>> = ({ children }) => <AbsoluteFill>{children}</AbsoluteFill>;

/** Hidden until `from` (0..1 of the transition), then shown. */
export const showFrom = (from: number): React.FC<SideProps<Params>> => {
  const C: React.FC<SideProps<Params>> = ({ progress, children }) => (progress < from ? null : <AbsoluteFill>{children}</AbsoluteFill>);
  return C;
};
