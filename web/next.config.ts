import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingIncludes: {
    "/api/boletin-area/national": ["./data/project-directory.json"],
    "/api/boletin-area/monthly": ["./public/data/madrid-licencias-*.geojson", "./public/data/madrid-licencias-index.json"],
    "/api/boletin-area/context": ["./data/project-directory.json", "./public/data/madrid-sigma-ambitos.geojson", "./public/data/madrid-sigma-visor-slim.json", "./public/data/madrid-sigma-map-cards.json"],
    "/api/boletin-area/project": ["./public/data/projects.json", "./public/data/madrid-sigma*.json"],
    "/proyectos": ["./data/project-directory.json"],
    "/proyectos/**/*": ["./data/project-directory.json"],
    "/proyecto/*": ["./data/project-directory.json"],
    "/admin/analitica": ["./data/project-directory.json"],
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
      // These datasets are fetched by the browser from the static CDN.
      "./public/data/madrid-licencias-20*.json",
      "./public/data/madrid-licencias-filter-rows.json",
      "./public/data/madrid-viso-expedientes.json",
      "./public/data/madrid-licencias-*.geojson",
      "./public/data/ubicaciones-map.geojson",
      "./public/data/sector-geometries.geojson",
    ],
  },
};

export default nextConfig;
