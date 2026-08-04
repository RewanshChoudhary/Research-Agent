// Minimal zero-dependency dev server for the Research-Agent frontend.
// Serves static files from this directory and proxies /api/* to the Spring API.
// Usage: node serve.js [port]

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = parseInt(process.argv[2] || process.env.FRONTEND_PORT || "3000", 10);
const API_TARGET = process.env.API_TARGET || "http://localhost:8080";

const ROOT = __dirname;
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".png": "image/png",
};

function proxy(req, res) {
  const url = new URL(API_TARGET + req.url);
  const options = {
    method: req.method,
    hostname: url.hostname,
    port: url.port,
    path: url.pathname + url.search,
    headers: req.headers,
  };
  const p = http.request(options, (pres) => {
    res.writeHead(pres.statusCode, pres.headers);
    pres.pipe(res);
  });
  p.on("error", (e) => {
    res.writeHead(502, { "Content-Type": "text/plain" });
    res.end("API proxy error: " + e.message);
  });
  req.pipe(p);
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith("/api/") || req.url.startsWith("/api")) {
    return proxy(req, res);
  }
  let pathname = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (pathname === "/") pathname = "/index.html";
  const filePath = path.join(ROOT, pathname);
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    return res.end("Forbidden");
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      return res.end("Not found: " + pathname);
    }
    res.writeHead(200, { "Content-Type": MIME[path.extname(filePath)] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log(`Frontend dev server on http://localhost:${PORT} (proxy -> ${API_TARGET})`);
});
