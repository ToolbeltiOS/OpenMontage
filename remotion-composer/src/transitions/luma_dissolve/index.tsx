import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Defs, defineTransition, ease, mix, paramDefaults, Pass, useSvgId } from '../core';
import meta from './transition.json';

type P = { softness: number; darkFirst: boolean };

/**
 * Scene A sits on top and loses alpha by its own brightness: alpha = (threshold - luma) / softness
 * (or the reverse for darkFirst). The threshold sweeps across the whole brightness range.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  exitingOnTop: true,
  Exiting: ({ progress, children, params: { softness: s, darkFirst } }) => {
    const id = useSvgId('luma');
    const e = ease.inOutCubic(progress);
    const k = darkFirst ? 1 / s : -1 / s;
    const thr = darkFirst ? mix(-s, 1, e) : mix(1 + s, 0, e);
    const offset = darkFirst ? -thr / s : thr / s;
    const row = `${0.2126 * k} ${0.7152 * k} ${0.0722 * k} 0 ${offset}`;
    return (
      <AbsoluteFill>
        <Defs>
          <filter id={id} colorInterpolationFilters="sRGB">
            <feColorMatrix in="SourceGraphic" type="matrix" values={`0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  ${row}`} result="m" />
            <feComposite in="SourceGraphic" in2="m" operator="in" />
          </filter>
        </Defs>
        <AbsoluteFill style={{ filter: `url(#${id})`, opacity: progress >= 1 ? 0 : 1 }}>{children}</AbsoluteFill>
      </AbsoluteFill>
    );
  },
  Entering: Pass,
});
