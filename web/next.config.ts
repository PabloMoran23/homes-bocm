import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingIncludes: {
    "/api/boletin-area/national": ["./data/project-directory.json"],
    "/api/boletin-area/context": ["./data/project-directory.json"],
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
  // public/data/* is served from Supabase Storage (lib/web-data.ts); a local
  // copy (build-data / pull-data) must never be bundled into functions.
  outputFileTracingExcludes: {
    "*": ["./public/data/**"],
  },
};

export default nextConfig;
