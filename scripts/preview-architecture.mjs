#!/usr/bin/env node
/**
 * Local preview server for docs/ARCHITECTURE_WORKFLOW.md (zero npm deps)
 * Usage: node scripts/preview-architecture.mjs
 */
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const mdPath = join(root, "docs", "ARCHITECTURE_WORKFLOW.md");
const port = 8765;

const md = readFileSync(mdPath, "utf8");

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>The Second Brain — Architecture Preview</title>
  <style>
    :root { color-scheme: light dark; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
      max-width: 960px;
      margin: 0 auto;
      padding: 2rem 1.5rem 4rem;
    }
    img { max-width: 100%; height: auto; }
    pre { overflow-x: auto; padding: 1rem; border-radius: 8px; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #8884; padding: 0.5rem 0.75rem; text-align: left; }
    .mermaid { margin: 1.5rem 0; text-align: center; }
    h1 { border-bottom: 1px solid #8884; padding-bottom: 0.3rem; }
  </style>
</head>
<body><div id="content">Loading…</div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

  const res = await fetch("/raw");
  const md = await res.text();
  document.getElementById("content").innerHTML = marked.parse(md, { gfm: true });

  mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "loose" });
  document.querySelectorAll("pre > code.language-mermaid").forEach((block) => {
    const div = document.createElement("div");
    div.className = "mermaid";
    div.textContent = block.textContent;
    block.closest("pre").replaceWith(div);
  });
  await mermaid.run({ querySelector: ".mermaid" });
</script>
</body>
</html>`;

const server = createServer((req, res) => {
  const url = req.url?.split("?")[0] ?? "/";

  if (url === "/" || url === "/index.html") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(html);
    return;
  }

  if (url === "/raw") {
    res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(md);
    return;
  }

  if (url.startsWith("/diagrams/")) {
    const file = join(root, "docs", url.slice(1));
    if (existsSync(file) && file.startsWith(join(root, "docs"))) {
      const ext = file.split(".").pop();
      const types = { svg: "image/svg+xml", mmd: "text/plain", png: "image/png" };
      res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream" });
      res.end(readFileSync(file));
      return;
    }
  }

  res.writeHead(404);
  res.end("Not found");
});

server.listen(port, () => {
  console.log(`Architecture preview: http://localhost:${port}`);
  console.log("Press Ctrl+C to stop.");
});
