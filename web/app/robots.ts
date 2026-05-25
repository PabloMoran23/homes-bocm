import type { MetadataRoute } from "next";
import { isPublicEdition } from "@/lib/edition";
import { getSiteUrl } from "@/lib/site-url";

const DEV_ONLY_DISALLOW = [
  "/admin",
  "/planes",
  "/fuentes",
  "/madrid/bocm",
  "/madrid/sigma",
  "/madrid/licencias",
  "/api/admin",
] as const;

export default function robots(): MetadataRoute.Robots {
  const base = getSiteUrl();

  if (!isPublicEdition()) {
    return {
      rules: { userAgent: "*", disallow: "/" },
    };
  }

  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/en-desarrollo", ...DEV_ONLY_DISALLOW],
    },
    sitemap: `${base}/sitemap.xml`,
  };
}
