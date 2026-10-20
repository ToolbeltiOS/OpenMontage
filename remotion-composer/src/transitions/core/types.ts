import type React from 'react';
import type { FC, ReactNode } from 'react';

export type Params = Record<string, unknown>;

/** Props each side of a transition receives. `progress` runs 0..1 over the transition (use linear timing). */
export type SideProps<P extends Params> = {
  progress: number;
  children: ReactNode;
  params: P;
  durationInFrames: number;
};

export type TransitionImpl<P extends Params> = {
  /** Default parameter values. Read them from transition.json with paramDefaults() so there is one source. */
  defaults: P;
  /** Wraps scene A (the outgoing scene). */
  Exiting: FC<SideProps<P>>;
  /** Wraps scene B (the incoming scene). */
  Entering: FC<SideProps<P>>;
  /** Draw scene A above scene B, e.g. when A breaks away to show B. Default: B is on top. */
  exitingOnTop?: boolean;
  /** Extra style for the wrapper of one side, e.g. a blend mode that must mix with the other scene. */
  sideStyle?: (side: 'exiting' | 'entering', progress: number, params: P) => React.CSSProperties;
};

export const defineTransition = <P extends Params>(impl: TransitionImpl<P>) => impl;

export type ParamSpec = { name: string; default: unknown };

/** Turns the "params" list of a transition.json into a defaults object. */
export const paramDefaults = <P extends Params>(meta: { params: readonly ParamSpec[] }): P =>
  Object.fromEntries(meta.params.map((p) => [p.name, p.default])) as P;

/** The shape of transition.json (see schema/transition.schema.json). */
export type TransitionMeta = {
  id: string;
  name: string;
  version: string;
  summary: string;
  uses: string[];
  family: string;
  subfamily: string;
  facets: {
    structure: string;
    origin: string;
    edge: string;
    layers: string;
    space: string;
    timing: string;
    tone: string[];
    function: string[];
    also: string[];
  };
  duration: { default: number; min: number; max: number };
  overlay: boolean;
  requires: string[];
  params: (ParamSpec & { type: string; description: string; min?: number; max?: number; options?: string[] })[];
  presets: { id: string; name: string; params: Params }[];
  authors: string[];
  changelog: { version: string; date: string; notes: string }[];
};
