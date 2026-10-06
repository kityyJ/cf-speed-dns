const GROUPS = new Set(["ct", "cu", "cmcc", "all"]);

function clamp(value, min, max, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function withCors(headers = {}) {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,HEAD,OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Cache-Control": "public, max-age=60, s-maxage=300",
    ...headers,
  };
}

async function readStatic(context, path) {
  const url = new URL(path, context.request.url);

  if (context.env && context.env.ASSETS && typeof context.env.ASSETS.fetch === "function") {
    return context.env.ASSETS.fetch(url);
  }

  return fetch(url, {
    headers: {
      "User-Agent": "cf-speed-dns-pages-function/1.0",
    },
  });
}

function normalizeLines(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export async function onRequest(context) {
  const request = context.request;
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: withCors() });
  }

  if (!["GET", "HEAD"].includes(request.method)) {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: withCors({ "Content-Type": "text/plain; charset=utf-8" }),
    });
  }

  const path = url.pathname.replace(/^\/+|\/+$/g, "");

  // Let normal static files pass through untouched.
  if (!GROUPS.has(path) && path !== "health") {
    return context.next();
  }

  if (path === "health") {
    const response = await readStatic(context, "/data/status.json");
    if (!response.ok) {
      return new Response(JSON.stringify({ ok: false }), {
        status: 503,
        headers: withCors({ "Content-Type": "application/json; charset=utf-8" }),
      });
    }

    const status = await response.text();
    return new Response(status, {
      status: 200,
      headers: withCors({ "Content-Type": "application/json; charset=utf-8" }),
    });
  }

  const limit = clamp(url.searchParams.get("ips"), 1, 100, 20);
  const format = (url.searchParams.get("format") || "text").toLowerCase();

  if (format === "json") {
    const response = await readStatic(context, `/api/${path}.json`);
    if (!response.ok) {
      return new Response(JSON.stringify({ error: "IP pool unavailable" }), {
        status: 503,
        headers: withCors({ "Content-Type": "application/json; charset=utf-8" }),
      });
    }

    const payload = await response.json();
    payload.items = (payload.items || []).slice(0, limit);
    payload.count = payload.items.length;

    return new Response(JSON.stringify(payload, null, 2), {
      status: 200,
      headers: withCors({ "Content-Type": "application/json; charset=utf-8" }),
    });
  }

  const response = await readStatic(context, `/api/${path}.txt`);
  if (!response.ok) {
    return new Response("IP pool unavailable\n", {
      status: 503,
      headers: withCors({ "Content-Type": "text/plain; charset=utf-8" }),
    });
  }

  const lines = normalizeLines(await response.text()).slice(0, limit);
  const body = lines.join("\n") + (lines.length ? "\n" : "");

  return new Response(request.method === "HEAD" ? null : body, {
    status: 200,
    headers: withCors({
      "Content-Type": "text/plain; charset=utf-8",
      "X-IP-Count": String(lines.length),
      "X-IP-Group": path,
    }),
  });
}
