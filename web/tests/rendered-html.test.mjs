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

test("interface preserves the v0.2 generation workflow", async () => {
  const [page, layout, css, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /Generate Lesson/);
  assert.match(page, /Generate Teaching Package/);
  assert.match(page, /Paste a lesson/);
  assert.match(page, /Build a preliminary Teacher Playbook/);
  assert.match(page, /Save Source/);
  assert.match(page, /Run Baseline Analysis/);
  assert.match(page, /Save Preliminary Playbook/);
  assert.match(page, /Enrich Playbook/);
  assert.match(page, /Enrichment options/);
  assert.match(page, /Baseline and enriched playbook/);
  assert.match(page, /Approve and Save Enriched Playbook/);
  assert.match(page, /\/api\/playbook-enrichments/);
  assert.match(page, /Build a renderer-neutral slide specification/);
  assert.match(page, /Generate Presentation Specification/);
  assert.match(page, /Approve and Save Presentation Specification/);
  assert.match(page, /presentation-spec/);
  assert.match(page, /data-testid="presentation-spec-planner"/);
  assert.match(page, /Original source text/);
  assert.match(page, /Extracted structured information/);
  assert.match(page, /Warnings and missing information/);
  assert.match(page, /Unclassified source text/);
  assert.match(page, /\/api\/pasted-lessons/);
  assert.match(page, /data-testid="pasted-lesson-view"/);
  assert.match(page, /Download Teacher Companion/);
  assert.match(page, /Publish to Google Docs/);
  assert.match(page, /Publish to Google Slides/);
  assert.match(page, /Lesson Generated Successfully/);
  assert.match(page, /Copy Gamma Prompt/);
  assert.match(page, /Download Gamma Prompt/);
  assert.match(page, /Open Gamma/);
  assert.match(page, /Open Gamma Agent/);
  assert.match(page, /navigator\.clipboard\.writeText/);
  assert.match(page, /\/api\/clipboard/);
  assert.match(page, /NEXT_PUBLIC_GAMMA_URL/);
  assert.match(page, /GammaDeckPrompt\.md/);
  assert.match(page, /Open Output Folder/);
  assert.match(page, /Open Renderer Prompt Bundle/);
  assert.match(page, /Generate Again/);
  assert.match(page, /Failed stage/);
  assert.match(page, /blocking_findings/);
  assert.match(page, /finding\.code/);
  assert.match(page, /finding\.severity/);
  assert.match(page, /finding\.message/);
  assert.match(page, /setInterval/);
  assert.match(page, /data-testid="generation-view"/);
  assert.match(page, /data-testid="complete-view"/);
  assert.match(layout, /title:\s*"TeacherOS — Lesson Generation"/);
  assert.match(css, /:root\[data-theme="dark"\]/);
  assert.match(css, /@media\s*\(max-width:\s*760px\)/);
  assert.match(packageJson, /"name": "teacheros-interface"/);
});
