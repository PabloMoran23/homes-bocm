import assert from "node:assert/strict";
import {
  analyticsHref,
  madridMidnight,
  parseAnalyticsQuery,
  requestedAnalyticsHref,
} from "../lib/analytics-filters.ts";

const now = new Date("2026-10-20T14:30:00Z");

const week = parseAnalyticsQuery({}, now);
assert.equal(week.range, "7d");
assert.equal(week.traffic, "all");
assert.equal(week.source, "all");
assert.equal(week.section, "all");
assert.equal(week.granularity, "day");
assert.equal(week.from.toISOString(), madridMidnight("2026-10-14").toISOString());
assert.equal(week.to.toISOString(), now.toISOString());
assert.equal(week.previousTo.toISOString(), week.from.toISOString());
assert.equal(week.previousFrom.toISOString(), new Date(week.from.getTime() - (week.to.getTime() - week.from.getTime())).toISOString());
assert.equal(analyticsHref(week), "/admin/analitica");

const day = parseAnalyticsQuery({ r: "24h" }, now);
assert.equal(day.granularity, "hour");
assert.equal(day.to.getTime() - day.from.getTime(), 24 * 60 * 60 * 1000);
assert.equal(analyticsHref(day), "/admin/analitica?r=24h");

const legacy = parseAnalyticsQuery({ days: "30", traffic: "unclassified", source: "google" }, now);
assert.equal(legacy.range, "30d");
assert.equal(legacy.traffic, "human");
assert.equal(legacy.source, "google");
assert.equal(analyticsHref(legacy), "/admin/analitica?r=30d&traffic=human&source=google");

const interesting = parseAnalyticsQuery({ traffic: "interesting" }, now);
assert.equal(interesting.traffic, "human");

const custom = parseAnalyticsQuery({ r: "custom", from: "2026-10-01", to: "2026-10-02" }, now);
assert.equal(custom.range, "custom");
assert.equal(custom.granularity, "hour");
assert.equal(custom.from.toISOString(), "2026-09-30T22:00:00.000Z");
assert.equal(custom.to.toISOString(), "2026-10-02T22:00:00.000Z");

const winter = madridMidnight("2026-01-15");
assert.equal(winter.toISOString(), "2026-01-14T23:00:00.000Z");
const summer = madridMidnight("2026-10-20");
assert.equal(summer.toISOString(), "2026-10-19T22:00:00.000Z");

const wide = parseAnalyticsQuery({ r: "custom", from: "2026-01-01", to: "2026-10-20" }, now);
assert.ok(wide.to.getTime() - wide.from.getTime() <= 90 * 24 * 60 * 60 * 1000);
assert.equal(wide.range, "custom");

const swapped = parseAnalyticsQuery({ r: "custom", from: "2026-10-18", to: "2026-10-10" }, now);
assert.equal(swapped.fromDate <= swapped.toDate, true);

assert.equal(requestedAnalyticsHref({ r: "7d" }), "/admin/analitica?r=7d");
assert.notEqual(requestedAnalyticsHref({ r: "7d" }), analyticsHref(parseAnalyticsQuery({ r: "7d" }, now)));

const human = parseAnalyticsQuery({ traffic: "bot", section: "proyecto" }, now);
assert.equal(analyticsHref(human, true), "/admin/analitica?traffic=bot&section=proyecto&muestra=1");

console.log("analytics filters ok");
