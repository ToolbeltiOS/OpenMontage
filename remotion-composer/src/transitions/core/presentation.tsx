import React from 'react';
import { AbsoluteFill } from 'remotion';
import type { TransitionPresentation, TransitionPresentationComponentProps } from '@remotion/transitions';
import type { Params, TransitionImpl } from './types';

const components = new WeakMap<object, React.FC<TransitionPresentationComponentProps<Params>>>();

const componentFor = <P extends Params>(impl: TransitionImpl<P>) => {
  let C = components.get(impl);
  if (!C) {
    const Comp: React.FC<TransitionPresentationComponentProps<Params>> = ({
      children,
      presentationDirection,
      presentationProgress,
      presentationDurationInFrames,
      passedProps,
    }) => {
      const Side = presentationDirection === 'exiting' ? impl.Exiting : impl.Entering;
      const onTop = impl.exitingOnTop ? presentationDirection === 'exiting' : presentationDirection === 'entering';
      return (
        <AbsoluteFill style={{ zIndex: onTop ? 1 : 0, ...impl.sideStyle?.(presentationDirection, presentationProgress, passedProps as P) }}>
          <Side progress={presentationProgress} params={passedProps as P} durationInFrames={presentationDurationInFrames}>
            {children}
          </Side>
        </AbsoluteFill>
      );
    };
    C = Comp;
    components.set(impl, C);
  }
  return C;
};

/**
 * Turns a transition into a <TransitionSeries> presentation.
 *
 *   <TransitionSeries.Transition presentation={toPresentation(liquidFill, { color: '#000' })}
 *     timing={linearTiming({ durationInFrames: 72 })} />
 *
 * Use linearTiming: every transition applies its own easing.
 */
export const toPresentation = <P extends Params>(impl: TransitionImpl<P>, params: Partial<P> = {}): TransitionPresentation<Params> => ({
  component: componentFor(impl),
  props: { ...impl.defaults, ...params },
});
