// Runtime deps already in package.json that ship without bundled types.
// Declared here so the buildability check runs under --noEmit without
// pulling extra @types packages.
declare module "d3-geo";
declare module "topojson-client";
declare module "world-atlas/land-110m.json";
