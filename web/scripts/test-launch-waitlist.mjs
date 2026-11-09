import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const code = ts.transpileModule(fs.readFileSync(new URL("../app/api/launch-waitlist/route.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const rows = [];
let storageError = false;
const fakeProcess = { env: { NEXT_PUBLIC_SUPABASE_URL: "https://example.test", NEXT_PUBLIC_SUPABASE_ANON_KEY: "test-anon", LAUNCH_WAITLIST_KEY: "test-only" } };
const routeModule = { exports: {} };
const requireMock = name => {
  if (name === "next/server") return { NextResponse: Response };
  if (name === "@supabase/supabase-js") return { createClient: () => ({
    rpc: async (name, params) => {
      assert.equal(name, "homes_launch_waitlist_register");
      assert.equal(params.p_key, "test-only");
      if (!storageError) rows.push({ email: params.p_email, source: params.p_source, context_key: params.p_context_key });
      return { error: storageError ? { code: "unavailable" } : null };
    },
  }) };
  throw new Error(`Unexpected module ${name}`);
};
vm.runInThisContext(`(function(require,module,exports,process){${code}\n})`)(requireMock, routeModule, routeModule.exports, fakeProcess);
const { POST } = routeModule.exports;
async function submit(body, origin = "http://localhost:3000") {
  const request = new Request("http://localhost:3000/api/launch-waitlist", {
    method: "POST", headers: { origin, "content-type": "application/json" }, body: JSON.stringify(body && { source: "boletin", ...body }),
  });
  request.nextUrl = new URL(request.url);
  return (await POST(request)).status;
}
assert.equal(await submit({ email: " Test@Example.com " }), 204);
assert.equal(rows[0].email, "test@example.com");
assert.equal(await submit({ email: "bad-email" }), 400);
assert.equal(await submit(null), 400);
assert.equal(await submit({ email: "test@example.com" }, "https://other.test"), 403);
assert.equal(await submit({ email: "test@example.com", website: "spam" }), 204);
assert.equal(rows.length, 1, "Honeypot and invalid requests must not write emails");
assert.equal(await submit({ email: "x".repeat(2100) }), 413);
assert.equal(await submit({ email: "test@example.com", source: "home" }), 400);
assert.equal(await submit({ email: "test@example.com", source: "project" }), 400);
assert.equal(await submit({ email: "test@example.com", source: "project", contextKey: "135-2018-00489" }), 204);
assert.equal(rows.at(-1).source, "project");
assert.equal(rows.at(-1).context_key, "135-2018-00489");
assert.equal(await submit({ email: "test@example.com", source: "dashboard", contextKey: "ignored" }), 204);
assert.equal(rows.at(-1).source, "dashboard");
assert.equal(rows.at(-1).context_key, "");
storageError = true;
assert.equal(await submit({ email: "test@example.com" }), 503, "Do not confirm an unsaved email");
delete fakeProcess.env.LAUNCH_WAITLIST_KEY;
assert.equal(await submit({ email: "test@example.com" }), 503);
console.log("Launch waitlist: validation, origin, honeypot, normalization and storage errors OK");
