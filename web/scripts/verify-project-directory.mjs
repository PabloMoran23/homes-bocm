/** Crawl the running directory through HTML links; no map interaction or sitemap.
 * Usage: node scripts/verify-project-directory.mjs http://localhost:3000
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const origin = process.argv[2] ?? "http://localhost:3000";
const data = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../data/project-directory.json", import.meta.url)),
    "utf8",
  ),
);
const expected = new Set(
  data.projects.map((p) => `/proyecto/${encodeURIComponent(p.id)}`),
);
const projectLinks = new Set();
const seen = new Set();
const queue = ["/"];
const decode = (s) => s.replaceAll("&amp;", "&");
const links = (html) =>
  [...html.matchAll(/<a\b[^>]*\bhref="([^"]+)"/g)].map((m) => decode(m[1]));
let pages = 0;
let maximumDepth = 0;
const depth = new Map([["/", 0]]);

while (queue.length) {
  const batch = queue.splice(0, 6).filter((path) => !seen.has(path));
  batch.forEach((path) => seen.add(path));
  await Promise.all(
    batch.map(async (path) => {
      const response = await fetch(new URL(path, origin), {
        signal: AbortSignal.timeout(60000),
      });
      assert.equal(response.status, 200, path);
      const html = await response.text();
      const currentDepth = depth.get(path);
      for (const href of links(html)) {
        const url = new URL(href, origin);
        if (url.origin !== new URL(origin).origin) continue;
        const target = url.pathname + url.search;
        if (url.pathname.startsWith("/proyecto/")) {
          if (expected.has(target)) {
            projectLinks.add(target);
            maximumDepth = Math.max(maximumDepth, currentDepth + 1);
          }
        } else if (
          url.pathname === "/proyectos" ||
          url.pathname.startsWith("/proyectos/")
        ) {
          if (!depth.has(target)) {
            depth.set(target, currentDepth + 1);
            queue.push(target);
          }
        }
      }
      if (path.startsWith("/proyectos")) {
        assert.match(html, /<h1\b/, `Missing title: ${path}`);
        const canonical = html.match(
          /<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"/,
        );
        assert.ok(canonical, `Missing canonical: ${path}`);
        const canonicalUrl = new URL(decode(canonical[1]));
        assert.equal(
          canonicalUrl.pathname + canonicalUrl.search,
          path,
          `Wrong canonical: ${path}`,
        );
      }
    }),
  );
  pages += batch.length;
  if (pages % 120 < 6)
    console.log(
      `${pages} páginas recorridas, ${projectLinks.size}/${expected.size} fichas enlazadas`,
    );
}
const missing = [...expected].filter((path) => !projectLinks.has(path));
assert.equal(
  missing.length,
  0,
  `Fichas huérfanas: ${missing.slice(0, 10).join(", ")}`,
);
for (const path of [
  "/proyectos/no-existe",
  "/proyectos/madrid/no-existe",
  "/proyectos/madrid/madrid?pagina=0",
  "/proyectos/madrid/madrid?pagina=999999",
  "/proyectos/madrid/madrid?pagina=2&pagina=3",
]) {
  const response = await fetch(new URL(path, origin));
  assert.equal(response.status, 404, `Expected 404: ${path}`);
}
const redirect = await fetch(
  new URL("/proyectos/madrid/madrid?pagina=1", origin),
  { redirect: "manual" },
);
assert.equal(redirect.status, 308);
assert.equal(
  new URL(redirect.headers.get("location"), origin).pathname,
  "/proyectos/madrid/madrid",
);

// Opt-in because real fichas still read their detail data from Supabase.
if (process.argv.includes("--details")) {
  for (const prefix of ["135-", "bocm:", "el-molar-proy-", "benidorm-proy-"]) {
    const project = data.projects.find((p) => p.id.startsWith(prefix));
    assert.ok(project, `Missing sample: ${prefix}`);
    const path = `/proyecto/${encodeURIComponent(project.id)}`;
    const response = await fetch(new URL(path, origin), {
      signal: AbortSignal.timeout(60000),
    });
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.ok(
      links(html).includes(`/proyectos/${project.municipality}`),
      `Missing territory navigation: ${path}`,
    );
    const relatedSection = html.match(
      /<section aria-label="Otros proyectos del municipio"[\s\S]*?<\/section>/,
    )?.[0];
    assert.ok(relatedSection, `Missing related projects: ${path}`);
    const related = links(relatedSection).filter((href) =>
      href.startsWith("/proyecto/"),
    );
    assert.ok(related.length > 0 && related.length <= 6);
    assert.ok(!related.includes(path), `Self recommendation: ${path}`);
    const canonical = html.match(
      /<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"/,
    );
    assert.ok(canonical);
    assert.equal(new URL(decode(canonical[1])).pathname, path);
    if (project.aliases.length) {
      const aliasResponse = await fetch(
        new URL(`/proyecto/${encodeURIComponent(project.aliases[0])}`, origin),
        { redirect: "manual" },
      );
      assert.equal(aliasResponse.status, 308, project.aliases[0]);
      assert.equal(
        new URL(aliasResponse.headers.get("location"), origin).pathname,
        path,
      );
    }
    console.log(`Ficha, navegación y canonical correctos: ${project.id}`);
  }
}
console.log(
  `OK: ${projectLinks.size} fichas accesibles desde Inicio; ${pages} páginas recorridas; profundidad máxima ${maximumDepth}; canonical, paginación y 404 verificados.`,
);
