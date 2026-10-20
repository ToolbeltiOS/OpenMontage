import React from 'react';
import { AbsoluteFill } from 'remotion';
import { bridged, ease, paramDefaults } from '../core';
import meta from './transition.json';

type P = { color: string; hold: number };

export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params }) => (
  <AbsoluteFill style={{ background: params.color, opacity: ease.inOutCubic(phase === 'in' ? progress : 1 - progress) }} />
));
