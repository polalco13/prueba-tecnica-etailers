/**
 * API de stock del proveedor (mock).
 * Node sin dependencias externas.
 *
 *   GET /health
 *   GET /api/v1/stock?page=1&per_page=50&updated_since=2026-01-01
 *        Cabecera obligatoria: Authorization: Bearer <STOCK_API_TOKEN>
 *
 * Comportamiento deliberado:
 *   - Pagina de 50 en 50 por defecto (maximo 100).
 *   - Devuelve 401 sin token valido.
 *   - Devuelve 500 de forma aleatoria (ERROR_RATE) para forzar reintentos.
 *   - Devuelve 429 con Retry-After si se superan las peticiones por minuto.
 *   - Latencia artificial variable.
 */
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT || 3001;
const TOKEN = process.env.STOCK_API_TOKEN || "etailers-demo-token";
const ERROR_RATE = Number(process.env.ERROR_RATE ?? 0.15);
const RATE_LIMIT = Number(process.env.RATE_LIMIT ?? 40); // peticiones por minuto

const stock = JSON.parse(fs.readFileSync(path.join(__dirname, "stock.json"), "utf8"));

let hits = [];

function rateLimited() {
  const now = Date.now();
  hits = hits.filter((t) => now - t < 60_000);
  hits.push(now);
  return hits.length > RATE_LIMIT;
}

function send(res, code, body, extraHeaders = {}) {
  const payload = JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    ...extraHeaders,
  });
  res.end(payload);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === "/health") {
    return send(res, 200, { status: "ok", records: stock.length });
  }

  if (url.pathname !== "/api/v1/stock") {
    return send(res, 404, { error: "not_found" });
  }

  const auth = req.headers.authorization || "";
  if (auth !== `Bearer ${TOKEN}`) {
    return send(res, 401, { error: "unauthorized", message: "Falta o es incorrecta la cabecera Authorization" });
  }

  if (rateLimited()) {
    return send(res, 429, { error: "rate_limited" }, { "Retry-After": "5" });
  }

  const latency = 80 + Math.floor(Math.random() * 400);

  setTimeout(() => {
    if (Math.random() < ERROR_RATE) {
      return send(res, 500, { error: "internal_error", message: "Fallo temporal del proveedor" });
    }

    const page = Math.max(1, parseInt(url.searchParams.get("page") || "1", 10));
    const perPage = Math.min(100, Math.max(1, parseInt(url.searchParams.get("per_page") || "50", 10)));
    const since = url.searchParams.get("updated_since");

    let rows = stock;
    if (since) {
      const d = new Date(since);
      if (!isNaN(d)) rows = rows.filter((r) => new Date(r.updated_at) >= d);
    }

    const total = rows.length;
    const start = (page - 1) * perPage;
    const slice = rows.slice(start, start + perPage);

    send(res, 200, {
      data: slice,
      meta: {
        page,
        per_page: perPage,
        total_records: total,
        total_pages: Math.ceil(total / perPage),
        has_next: start + perPage < total,
      },
    });
  }, latency);
});

server.listen(PORT, () => {
  console.log(`Stock API escuchando en http://localhost:${PORT}`);
  console.log(`Token: ${TOKEN} | error_rate: ${ERROR_RATE} | rate_limit: ${RATE_LIMIT}/min`);
});
