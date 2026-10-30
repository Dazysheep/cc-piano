// 本地预览用的零依赖静态服务器：node server.js
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = 8080;
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml" };

http
  .createServer((req, res) => {
    const urlPath = decodeURIComponent(req.url.split("?")[0]);
    const file = path.join(__dirname, urlPath === "/" ? "index.html" : urlPath);
    if (!file.startsWith(__dirname)) return res.writeHead(403).end();
    fs.readFile(file, (err, data) => {
      if (err) return res.writeHead(404).end("Not found");
      res.writeHead(200, { "Content-Type": (TYPES[path.extname(file)] || "application/octet-stream") + "; charset=utf-8" });
      res.end(data);
    });
  })
  .listen(PORT, () => console.log(`博客已启动：http://localhost:${PORT}`));
