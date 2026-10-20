import React, { useId } from 'react';

/** A unique, CSS-safe id for SVG filters and masks. */
export const useSvgId = (prefix: string) => `${prefix}-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;

/** Zero-size inline SVG that holds <defs> (filters, masks) for HTML elements to reference. */
export const Defs: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
    <defs>{children}</defs>
  </svg>
);
