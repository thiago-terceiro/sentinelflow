import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import sitemap from "../app/sitemap.ts";
import { getStructuredDataGraph } from "../lib/geo.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("sitemap returns valid canonical URLs with priorities", () => {
  try {
    const entries = sitemap();
    assert.ok(Array.isArray(entries));
    assert.ok(entries.length >= 8);

    const urls = entries.map((e) => e.url);
    assert.ok(urls.includes("https://sentinelflow.dev"));
    assert.ok(urls.includes("https://sentinelflow.dev/disputes"));
    assert.ok(urls.includes("https://sentinelflow.dev/telecom"));
    assert.ok(urls.includes("https://sentinelflow.dev/audit"));
    assert.ok(urls.includes("https://sentinelflow.dev/llms.txt"));
    assert.ok(urls.includes("https://sentinelflow.dev/llms-full.txt"));
    assert.ok(urls.includes("https://sentinelflow.dev/.well-known/mcp.json"));
    assert.ok(urls.includes("https://sentinelflow.dev/api/v1/geo/metadata"));

    const rootEntry = entries.find((e) => e.url === "https://sentinelflow.dev");
    assert.equal(rootEntry?.priority, 1.0);
    assert.equal(rootEntry?.changeFrequency, "daily");
  } catch (err) {
    assert.fail(err instanceof Error ? err.message : String(err));
  }
});

test("public sitemap.xml exists and matches expected format", () => {
  try {
    const sitemapPath = path.resolve(__dirname, "../public/sitemap.xml");
    assert.ok(fs.existsSync(sitemapPath), "public/sitemap.xml must exist");

    const xml = fs.readFileSync(sitemapPath, "utf-8");
    assert.ok(xml.includes("<urlset"));
    assert.ok(xml.includes("<loc>https://sentinelflow.dev</loc>"));
    assert.ok(xml.includes("<loc>https://sentinelflow.dev/disputes</loc>"));
    assert.ok(xml.includes("<loc>https://sentinelflow.dev/api/v1/geo/metadata</loc>"));
  } catch (err) {
    assert.fail(err instanceof Error ? err.message : String(err));
  }
});

test("getStructuredDataGraph returns valid JSON-LD graph with stacked schema", () => {
  try {
    const graphData = getStructuredDataGraph();

    assert.equal(graphData["@context"], "https://schema.org");
    assert.ok(Array.isArray(graphData["@graph"]));

    const types = graphData["@graph"].map((node) => node["@type"]);
    assert.ok(types.includes("SoftwareApplication"));
    assert.ok(types.includes("Organization"));
    assert.ok(types.includes("FAQPage"));
    assert.ok(types.includes("HowTo"));
    assert.ok(types.includes("WebSite"));

    const software = graphData["@graph"].find((n) => n["@type"] === "SoftwareApplication");
    assert.equal(software?.name, "SentinelFlow & SentinelPulse");
    assert.ok(Array.isArray(software?.featureList));
    assert.ok(software?.featureList.length >= 5);

    const faq = graphData["@graph"].find((n) => n["@type"] === "FAQPage");
    assert.ok(Array.isArray(faq?.mainEntity));
    assert.ok(faq?.mainEntity.length >= 5);
    const questions = faq?.mainEntity.map((q) => q.name);
    assert.ok(questions?.includes("What is SentinelFlow?"));
    assert.ok(questions?.includes("What is SentinelPulse?"));

    const howTo = graphData["@graph"].find((n) => n["@type"] === "HowTo");
    assert.equal(howTo?.name, "How to Investigate a Transaction Dispute with SentinelFlow");
    assert.ok(Array.isArray(howTo?.step));
    assert.equal(howTo?.step.length, 5);
  } catch (err) {
    assert.fail(err instanceof Error ? err.message : String(err));
  }
});
