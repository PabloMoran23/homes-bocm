import assert from "node:assert/strict";
import { register } from "node:module";
register(new URL("./ts-resolve-hook.mjs", import.meta.url).href, import.meta.url);

const {
  HEAVY_ROUTE_MAX_REQUESTS,
  classifyUserAgent,
  clientIpFrom,
  createFixedWindowLimiter,
  decideAccess,
  isHeavyRoute,
} = await import("../lib/bot-guard.ts");

const CHROME =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
const SAFARI =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15";
const FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0";
const CUBOT =
  "Mozilla/5.0 (Linux; Android 10; CUBOT_X30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36";

const BLOCKED = [
  "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
  "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ChatGPT-User/1.0; +https://openai.com/bot)",
  "ClaudeBot/1.0",
  "Mozilla/5.0 (compatible; Claude-Web/1.0)",
  "CCBot/2.0 (+https://commoncrawl.org/faq/)",
  "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; https://zhanzhang.toutiao.com/)",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/600.2.5 (KHTML, like Gecko) Version/8.0.2 Safari/600.2.5 (Amazonbot/0.1)",
  "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
  "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
  "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
  "Mozilla/5.0 (compatible; MJ12bot/v1.4.8; http://mj12bot.com/)",
  "Mozilla/5.0 (compatible; DotBot/1.2; +https://opensiteexplorer.org/dotbot)",
  "Mozilla/5.0 (Linux; Android 7.0;) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; PetalBot;+https://webmaster.petalsearch.com/site/petalbot)",
  "Mozilla/5.0 (compatible; Google-Extended; +http://www.google.com/bot.html)",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 (Applebot-Extended/1.0)",
  "python-requests/2.32.3",
  "Python-urllib/3.11",
  "curl/8.7.1",
  "curl",
  "Wget/1.21.4",
  "Go-http-client/1.1",
  "axios/1.7.2",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/122.0.0.0 Safari/537.36",
  "MyResearchBot/1.0",
  "SomeCrawler/2.0",
  "Java/17.0.10",
  "",
  "   ",
];

const GOOGLE = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)";
const BING = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)";
const GOOGLE_IP = "192.178.4.10";
const BING_IP = "157.55.39.10";
// First host of 142.250.32.0/27 from user-triggered-fetchers-google.json.
// That prefix is not in the other three Google lists.
const GOOGLE_FETCHER_IP = "142.250.32.1";

const ALLOWED = [
  CHROME,
  SAFARI,
  FIREFOX,
  CUBOT,
  "Mozilla/5.0 (compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)",
  "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
  "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
  "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
  "Twitterbot/1.0",
  "LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)",
  "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
  "WhatsApp/2.23.20.0 A",
  "TelegramBot (like TwitterBot)",
  "Mozilla/5.0 (compatible; words JavaScript/1.0; not a client)",
];

for (const ua of BLOCKED) assert.equal(classifyUserAgent(ua), "block", ua || "(empty)");
for (const ua of ALLOWED) assert.equal(classifyUserAgent(ua), "allow", ua);
assert.equal(classifyUserAgent(null), "block");
assert.equal(classifyUserAgent(GOOGLE), "verify-google");
assert.equal(classifyUserAgent("Googlebot-Image/1.0"), "verify-google");
assert.equal(classifyUserAgent("Mozilla/5.0 (compatible; Google-InspectionTool/1.0;)"), "verify-google");
assert.equal(classifyUserAgent(BING), "verify-bing");

assert.equal(isHeavyRoute("/proyecto/101"), true);
assert.equal(isHeavyRoute("/ubicacion/11000001"), true);
assert.equal(isHeavyRoute("/api/boletin-area"), true);
assert.equal(isHeavyRoute("/api/dominio/madrid-sigma"), true);
assert.equal(isHeavyRoute("/api/analytics"), true);
assert.equal(isHeavyRoute("/explore"), false);
assert.equal(isHeavyRoute("/proyectos/madrid"), false);
assert.equal(isHeavyRoute("/"), false);

const headers = new Headers({
  "x-real-ip": "203.0.113.10",
  "x-forwarded-for": "1.2.3.4, 203.0.113.10",
});
assert.equal(clientIpFrom(headers), "203.0.113.10");
assert.equal(
  clientIpFrom(new Headers({ "x-forwarded-for": "1.2.3.4, 198.51.100.8" })),
  "198.51.100.8",
);
assert.equal(
  clientIpFrom(new Headers({ "x-vercel-forwarded-for": "198.51.100.9, 10.0.0.1" })),
  "198.51.100.9",
);

async function main() {
  const limiter = createFixedWindowLimiter(HEAVY_ROUTE_MAX_REQUESTS, 60_000);
  const now = 1_700_000_000_000;
  for (let i = 0; i < HEAVY_ROUTE_MAX_REQUESTS; i += 1) {
    const decision = await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: CHROME,
      ip: "203.0.113.10",
      now,
      limiter,
    });
    assert.equal(decision.action, "allow");
  }
  const limited = await decideAccess({
    pathname: "/proyecto/abc",
    userAgent: CHROME,
    ip: "203.0.113.10",
    now: now + 1000,
    limiter,
  });
  assert.equal(limited.action, "rate_limit");
  if (limited.action === "rate_limit") assert.ok(limited.retryAfterSec >= 1 && limited.retryAfterSec <= 60);

  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: GOOGLE,
      ip: "203.0.113.10",
      now,
      limiter,
    })).action,
    "block",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: GOOGLE,
      ip: GOOGLE_IP,
      now,
      limiter,
    })).action,
    "allow",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: GOOGLE,
      ip: GOOGLE_FETCHER_IP,
      now,
      limiter,
    })).action,
    "allow",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: BING,
      ip: BING_IP,
      now,
      limiter,
    })).action,
    "allow",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: GOOGLE,
      ip: "203.0.113.10",
      headers: new Headers({ "x-vercel-verified-bot": "1" }),
      now: now + 1000,
      limiter,
    })).action,
    "block",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/",
      userAgent: "Mozilla/5.0 (compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)",
      ip: "203.0.113.50",
      now,
      limiter,
    })).action,
    "allow",
  );

  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: CHROME,
      ip: "203.0.113.11",
      now,
      limiter,
    })).action,
    "allow",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/",
      userAgent: CHROME,
      ip: "203.0.113.10",
      now,
      limiter,
    })).action,
    "allow",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: "curl/8.7.1",
      ip: "203.0.113.12",
      now,
      limiter,
    })).action,
    "block",
  );
  assert.equal(
    (await decideAccess({
      pathname: "/proyecto/abc",
      userAgent: CHROME,
      ip: "203.0.113.10",
      now: now + 60_000,
      limiter,
    })).action,
    "allow",
  );

  console.log("bot-guard ok");
}

await main();
