/**
 * Edge bot policy for pages that call Supabase.
 *
 * The browser session marker (`navigator.webdriver` in `lib/session-analytics.ts`)
 * only exists after HTML/JS has already run the project RPCs. Middleware therefore
 * reuses the same idea as `app/api/analytics/route.ts` (bot / crawler / spider /
 * headless) and applies it to the User-Agent before those RPCs.
 *
 * Googlebot and Bingbot are allowed only when the IP is in the published crawler
 * ranges, or when Vercel sets `x-vercel-verified-bot` (it strips that header from
 * clients). A User-Agent that only claims those bots is blocked. Social preview
 * bots stay on the User-Agent allow list. UptimeRobot is allowed.
 */

import { ipInSearchBotRanges, refreshSearchBotRanges } from "./search-bot-ranges";

type BotRule = {
  /** Lowercase substring matched against the User-Agent. */
  token: string;
  /** When set, `robots.txt` disallows this agent. */
  robots?: string;
};

const BLOCKED_BOTS: readonly BotRule[] = [
  { token: "gptbot", robots: "GPTBot" },
  { token: "chatgpt-user", robots: "ChatGPT-User" },
  { token: "oai-searchbot", robots: "OAI-SearchBot" },
  { token: "claudebot", robots: "ClaudeBot" },
  { token: "claude-web", robots: "Claude-Web" },
  { token: "anthropic-ai", robots: "anthropic-ai" },
  { token: "ccbot", robots: "CCBot" },
  { token: "bytespider", robots: "Bytespider" },
  { token: "amazonbot", robots: "Amazonbot" },
  { token: "perplexitybot", robots: "PerplexityBot" },
  { token: "perplexity-user", robots: "Perplexity-User" },
  { token: "google-extended", robots: "Google-Extended" },
  { token: "google-cloudvertexbot", robots: "Google-CloudVertexBot" },
  { token: "applebot-extended", robots: "Applebot-Extended" },
  { token: "meta-externalagent", robots: "Meta-ExternalAgent" },
  { token: "meta-externalfetcher", robots: "Meta-ExternalFetcher" },
  { token: "cohere-ai", robots: "cohere-ai" },
  { token: "diffbot", robots: "Diffbot" },
  { token: "imagesiftbot", robots: "ImagesiftBot" },
  { token: "omgili", robots: "omgili" },
  { token: "omgilibot", robots: "omgilibot" },
  { token: "youbot", robots: "YouBot" },
  { token: "petalbot", robots: "PetalBot" },
  { token: "aspiegelbot", robots: "AspiegelBot" },
  { token: "ahrefsbot", robots: "AhrefsBot" },
  { token: "ahrefssiteaudit", robots: "AhrefsSiteAudit" },
  { token: "semrushbot", robots: "SemrushBot" },
  { token: "mj12bot", robots: "MJ12bot" },
  { token: "dotbot", robots: "DotBot" },
  { token: "blexbot", robots: "BLEXBot" },
  { token: "dataforseobot", robots: "DataForSeoBot" },
  { token: "megaindex", robots: "MegaIndex" },
  { token: "serpstatbot", robots: "SerpstatBot" },
  { token: "sistrix", robots: "Sistrix" },
  { token: "rogerbot", robots: "rogerbot" },
  { token: "seokicks", robots: "SEOkicks" },
  { token: "linkdexbot", robots: "LinkdexBot" },
  { token: "zoominfobot", robots: "ZoominfoBot" },
  { token: "headlesschrome" },
  { token: "phantomjs" },
  { token: "puppeteer" },
  { token: "playwright" },
  { token: "selenium" },
  { token: "python-requests" },
  { token: "python-urllib" },
  { token: "aiohttp" },
  { token: "go-http-client" },
  { token: "node-fetch" },
  { token: "undici" },
  { token: "scrapy" },
  { token: "libwww-perl" },
  { token: "okhttp" },
  { token: "fasthttp" },
  { token: "mechanize" },
  { token: "nutch" },
  { token: "libcurl" },
  { token: "postmanruntime" },
];

/** Claimed Google crawlers. Allowed only after an IP or platform check. */
const GOOGLE_CLAIM_TOKENS = [
  "googlebot",
  "storebot-google",
  "google-inspectiontool",
  "googleother",
  "adsbot-google",
  "mediapartners-google",
  "feedfetcher-google",
  "apis-google",
] as const;

const BING_CLAIM_TOKENS = ["bingbot", "adidxbot", "bingpreview", "msnbot"] as const;

/** Preview and other agents. Checked only after the block list, so `Applebot-Extended` stays blocked. */
const ALLOWED_UA_TOKENS = [
  "uptimerobot",
  "duckduckbot",
  "applebot",
  "yandexbot",
  "yandeximages",
  "facebookexternalhit",
  "facebot",
  "twitterbot",
  "linkedinbot",
  "slackbot",
  "whatsapp",
  "telegrambot",
  "discordbot",
  "pinterestbot",
  "redditbot",
  "embedly",
  "skypeuripreview",
  "ia_archiver",
  "archive.org_bot",
] as const;

/** Short client names. Require a boundary so they don't match inside longer product tokens. */
const SCRIPTED_RE = /(?:^|[^a-z0-9])(?:curl|wget|axios|httpx|httpie|java)(?:\/|\s|$)/i;

/**
 * Unknown automation: a token ending in bot/crawler/spider/scraper (`FooBot/1.0`, `SomeCrawler/2.0`).
 * `CUBOT_X30` does not match, because "bot" is followed by "_" rather than a separator.
 */
const UNKNOWN_BOT_RE =
  /(?:^|[^a-z0-9])[a-z0-9-]*(?:bot|crawler|spider|scraper|scraping)(?:\/|\s|;|$)/i;

export const ROBOTS_BLOCKED_AGENTS: readonly string[] = BLOCKED_BOTS.flatMap((rule) =>
  rule.robots ? [rule.robots] : [],
);

/** Project pages and routes whose render calls Supabase RPCs. */
export const HEAVY_ROUTE_MAX_REQUESTS = 120;
export const HEAVY_ROUTE_WINDOW_MS = 60_000;

export type AccessDecision =
  | { action: "allow" }
  | { action: "block" }
  | { action: "rate_limit"; retryAfterSec: number };

export type UserAgentClass = "allow" | "block" | "verify-google" | "verify-bing";

export function classifyUserAgent(userAgent: string | null | undefined): UserAgentClass {
  const ua = (userAgent ?? "").trim().toLowerCase();
  if (!ua) return "block";
  if (BLOCKED_BOTS.some((rule) => ua.includes(rule.token))) return "block";
  if (SCRIPTED_RE.test(ua)) return "block";
  if (GOOGLE_CLAIM_TOKENS.some((token) => ua.includes(token))) return "verify-google";
  if (BING_CLAIM_TOKENS.some((token) => ua.includes(token))) return "verify-bing";
  if (ALLOWED_UA_TOKENS.some((token) => ua.includes(token))) return "allow";
  if (UNKNOWN_BOT_RE.test(ua)) return "block";
  return "allow";
}

export function isHeavyRoute(pathname: string): boolean {
  return (
    pathname === "/proyecto" ||
    pathname.startsWith("/proyecto/") ||
    pathname === "/ubicacion" ||
    pathname.startsWith("/ubicacion/") ||
    pathname === "/api/boletin-area" ||
    pathname.startsWith("/api/boletin-area/") ||
    pathname === "/api/dominio" ||
    pathname.startsWith("/api/dominio/") ||
    pathname === "/api/analytics" ||
    pathname.startsWith("/api/analytics/")
  );
}

type HeaderSource = { get(name: string): string | null };

function platformVerifiedBot(headers: HeaderSource | undefined): boolean {
  const value = headers?.get("x-vercel-verified-bot")?.trim().toLowerCase();
  return value === "1" || value === "true";
}

type CacheStorageLike = { open(name: string): Promise<CacheLike> };
type CacheLike = {
  match(request: string): Promise<{ text(): Promise<string> } | undefined>;
  put(request: string, response: Response): Promise<void>;
};

async function sharedHeavyLimit(
  ip: string,
  now: number,
): Promise<{ allowed: boolean; retryAfterSec: number } | null> {
  const cachesApi = (globalThis as { caches?: CacheStorageLike }).caches;
  if (!cachesApi?.open) return null;
  const windowStart = Math.floor(now / HEAVY_ROUTE_WINDOW_MS);
  const retryAfterSec = Math.max(1, Math.ceil((HEAVY_ROUTE_WINDOW_MS - (now % HEAVY_ROUTE_WINDOW_MS)) / 1000));
  const key = `https://homes-bot-limit.internal/${encodeURIComponent(ip)}/${windowStart}`;
  try {
    const cache = await cachesApi.open("homes-bot-limit");
    const hit = await cache.match(key);
    const count = hit ? Number(await hit.text()) : 0;
    if (count >= HEAVY_ROUTE_MAX_REQUESTS) return { allowed: false, retryAfterSec };
    await cache.put(key, new Response(String(count + 1)));
    return { allowed: true, retryAfterSec: 0 };
  } catch {
    return null;
  }
}

/**
 * Prefer Vercel-set client IPs. The left-most `x-forwarded-for` value is
 * client-supplied, so it is not used as the rate-limit key.
 */
export function clientIpFrom(headers: HeaderSource): string {
  const real = headers.get("x-real-ip")?.trim();
  if (real) return real;
  const vercel = headers.get("x-vercel-forwarded-for");
  if (vercel) {
    const first = vercel.split(",")[0]?.trim();
    if (first) return first;
  }
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) {
    const parts = forwarded.split(",").map((part) => part.trim()).filter(Boolean);
    const last = parts[parts.length - 1];
    if (last) return last;
  }
  return "unknown";
}

type Bucket = { count: number; resetAt: number };

export function createFixedWindowLimiter(limit: number, windowMs: number) {
  const buckets = new Map<string, Bucket>();

  return {
    check(key: string, now: number): { allowed: boolean; retryAfterSec: number } {
      if (buckets.size > 4000) {
        for (const [bucketKey, bucket] of buckets) {
          if (now >= bucket.resetAt) buckets.delete(bucketKey);
        }
        if (buckets.size > 4000) buckets.clear();
      }

      const current = buckets.get(key);
      if (!current || now >= current.resetAt) {
        buckets.set(key, { count: 1, resetAt: now + windowMs });
        return { allowed: true, retryAfterSec: 0 };
      }
      if (current.count >= limit) {
        return {
          allowed: false,
          retryAfterSec: Math.max(1, Math.ceil((current.resetAt - now) / 1000)),
        };
      }
      current.count += 1;
      return { allowed: true, retryAfterSec: 0 };
    },
  };
}

const heavyRouteLimiter = createFixedWindowLimiter(HEAVY_ROUTE_MAX_REQUESTS, HEAVY_ROUTE_WINDOW_MS);

export async function decideAccess(input: {
  pathname: string;
  userAgent: string | null;
  ip: string;
  now?: number;
  headers?: HeaderSource;
  limiter?: ReturnType<typeof createFixedWindowLimiter>;
}): Promise<AccessDecision> {
  const kind = classifyUserAgent(input.userAgent);
  if (kind === "block") return { action: "block" };
  if (kind === "verify-google" || kind === "verify-bing") {
    refreshSearchBotRanges(input.now);
    const vendor = kind === "verify-google" ? "google" : "bing";
    const verified = platformVerifiedBot(input.headers) || ipInSearchBotRanges(vendor, input.ip || "");
    if (!verified) return { action: "block" };
    return { action: "allow" };
  }
  if (!isHeavyRoute(input.pathname)) return { action: "allow" };

  const now = input.now ?? Date.now();
  if (!input.limiter) {
    const shared = await sharedHeavyLimit(input.ip || "unknown", now);
    if (shared) {
      if (!shared.allowed) return { action: "rate_limit", retryAfterSec: shared.retryAfterSec };
      return { action: "allow" };
    }
  }

  const limiter = input.limiter ?? heavyRouteLimiter;
  const result = limiter.check(input.ip || "unknown", now);
  if (!result.allowed) return { action: "rate_limit", retryAfterSec: result.retryAfterSec };
  return { action: "allow" };
}
