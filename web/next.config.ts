import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingIncludes: {
    "/proyectos": ["./data/project-directory.json"],
    "/proyectos/**/*": ["./data/project-directory.json"],
    "/proyecto/*": ["./data/project-directory.json"],
  },
  async redirects() {
    return [
      {
        source: "/madrid",
        destination: "/explore",
        permanent: true,
      },
      {
        source: "/sigma/:slug*",
        destination: "/proyecto/:slug*",
        permanent: true,
      },
    ];
  },
  outputFileTracingExcludes: {
    "*": [
      "./public/data/madrid-licencias-*.geojson",
      "./public/data/ubicaciones-map.geojson",
      "./public/data/sector-geometries.geojson",
    ],
  },
};

export default nextConfig;
