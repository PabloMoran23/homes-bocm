import type { MetadataRoute } from "next";
import { ROBOTS_BLOCKED_AGENTS } from "@/lib/bot-guard";
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

  const disallow = ["/en-desarrollo", ...DEV_ONLY_DISALLOW];
  // Google and Bing ignore crawl-delay. Yandex and several smaller crawlers honor it.
  const crawlDelay = 10;

  return {
    rules: [
      {
        userAgent: ["Googlebot", "Bingbot", "DuckDuckBot", "Applebot"],
        allow: "/",
        disallow,
      },
      {
        userAgent: "YandexBot",
        allow: "/",
        disallow,
        crawlDelay,
      },
      {
        userAgent: [...ROBOTS_BLOCKED_AGENTS],
        disallow: "/",
      },
      {
        userAgent: "*",
        allow: "/",
        disallow,
        crawlDelay,
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
