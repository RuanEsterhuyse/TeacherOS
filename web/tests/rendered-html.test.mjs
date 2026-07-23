import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the TeacherOS application shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>TeacherOS — Lesson Generation<\/title>/i);
  assert.match(html, /TeacherOS/);
  assert.match(html, /class="state-card"/);
});

test("interface preserves the v0.1 generation workflow", async () => {
  const [page, layout, css, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /Generate Lesson/);
  assert.match(page, /Lesson Generated Successfully/);
  assert.match(page, /Open Output Folder/);
  assert.match(page, /Open RendererPromptBundle\.md/);
  assert.match(page, /Generate Another Lesson/);
  assert.match(page, /setInterval/);
  assert.match(page, /data-testid="generation-view"/);
  assert.match(page, /data-testid="complete-view"/);
  assert.match(layout, /title:\s*"TeacherOS — Lesson Generation"/);
  assert.match(css, /:root\[data-theme="dark"\]/);
  assert.match(css, /@media\s*\(max-width:\s*760px\)/);
  assert.match(packageJson, /"name": "teacheros-interface"/);
});
