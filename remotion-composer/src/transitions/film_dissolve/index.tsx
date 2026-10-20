import React from 'react';
import { AbsoluteFill } from 'remotion';
import { clamp, defineTransition, ease, paramDefaults } from '../core';
import meta from './transition.json';

type P = Record<string, never>;

/** Additive dissolve: B is added on top of A (plus-lighter), so the middle glows. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  sideStyle: (side) => (side === 'entering' ? { mixBlendMode: 'plus-lighter' } : {}),
  Exiting: ({ progress, children }) => <AbsoluteFill style={{ opacity: clamp(2 * (1 - ease.inOutCubic(progress))) }}>{children}</AbsoluteFill>,
  Entering: ({ progress, children }) => <AbsoluteFill style={{ opacity: clamp(2 * ease.inOutCubic(progress)) }}>{children}</AbsoluteFill>,
});
