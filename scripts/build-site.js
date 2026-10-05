#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SITE_JSON = path.join(ROOT, "site.json");
const CNAME_FILE = path.join(ROOT, "CNAME");
const FUNNELS_DIR = path.join(ROOT, "funnels");
const OUT_DIR = path.join(ROOT, "_site");
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

function loadConfig() {
  if (!fs.existsSync(SITE_JSON)) fail("site.json is missing");
  let config;
  try {
    config = JSON.parse(fs.readFileSync(SITE_JSON, "utf8"));
  } catch (error) {
    fail(`site.json is not valid JSON: ${error.message}`);
  }
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    fail("site.json must be an object");
  }
  if (!Array.isArray(config.funnels) || config.funnels.length === 0) {
    fail("site.json must list at least one funnel");
  }
  return config;
}

function publishedFunnels(config) {
  const domain = String(config.domain || "").trim();
  const cname = fs.existsSync(CNAME_FILE)
    ? fs.readFileSync(CNAME_FILE, "utf8").trim()
    : "";
  if (!domain) fail("site.json is missing domain");
  if (domain !== cname) {
    fail(`CNAME (${JSON.stringify(cname)}) does not match site.json domain (${JSON.stringify(domain)})`);
  }

  const seenSlugs = new Set();
  const seenPaths = new Map();
  const published = [];

  config.funnels.forEach((funnel, index) => {
    if (!funnel || typeof funnel !== "object" || Array.isArray(funnel)) {
      fail(`funnels[${index}] must be an object`);
    }
    const slug = String(funnel.slug || "").trim();
    if (!SLUG_RE.test(slug)) {
      fail(`funnels[${index}] has an invalid slug: ${JSON.stringify(slug)}`);
    }
    if (seenSlugs.has(slug)) fail(`duplicate slug: ${slug}`);
    seenSlugs.add(slug);

    if (funnel.publish !== true) {
      console.log(`skip ${slug} (not published)`);
      return;
    }

    const source = path.join(FUNNELS_DIR, slug);
    const indexHtml = path.join(source, "index.html");
    if (!fs.existsSync(indexHtml) || fs.statSync(indexHtml).size === 0) {
      fail(`${slug} is missing funnels/${slug}/index.html`);
    }
    const html = fs.readFileSync(indexHtml, "utf8");
    if (!html.toLowerCase().includes("<html")) {
      fail(`funnels/${slug}/index.html does not look like HTML`);
    }

    const serveAt = String(funnel.serveAt || `/${slug}`).replace(/\/+$/, "") || "/";
    if (serveAt !== "/" && serveAt !== `/${slug}`) {
      fail(`${slug} has an unsupported serveAt: ${JSON.stringify(serveAt)}`);
    }
    if (seenPaths.has(serveAt)) {
      fail(`${slug} and ${seenPaths.get(serveAt)} both publish at ${serveAt}`);
    }
    seenPaths.set(serveAt, slug);
    published.push({ slug, source, serveAt });
    console.log(`ok ${slug} -> ${serveAt}`);
  });

  if (published.length === 0) fail("no published funnels");
  return published;
}

function copyDir(source, destination) {
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) copyDir(from, to);
    else fs.copyFileSync(from, to);
  }
}

function assemble(published) {
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  for (const funnel of published) {
    copyDir(funnel.source, path.join(OUT_DIR, funnel.slug));
    if (funnel.serveAt === "/") {
      fs.copyFileSync(
        path.join(funnel.source, "index.html"),
        path.join(OUT_DIR, "index.html")
      );
    }
  }

  fs.copyFileSync(CNAME_FILE, path.join(OUT_DIR, "CNAME"));
  fs.writeFileSync(path.join(OUT_DIR, ".nojekyll"), "");
  console.log("built _site");
}

function main() {
  const checkOnly = process.argv.includes("--check");
  const published = publishedFunnels(loadConfig());
  if (!checkOnly) assemble(published);
}

main();
