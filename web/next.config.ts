import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingExcludes: {
    "*": [
      "./public/data/madrid-licencias-*.geojson",
      "./public/data/ubicaciones-map.geojson",
      "./public/data/sector-geometries.geojson",
    ],
  },
};

export default nextConfig;
