/**
 * Cozly Media — free-slots proxy
 *
 * Why this exists: the funnel page is static and lives on cozlymedia.com.
 * It cannot call GoHighLevel directly — GHL's API needs a private token,
 * which must never ship in page source, and it sends no CORS headers for
 * a browser on another origin.
 *
 * This Worker sits in between. It holds the token server-side, asks GHL
 * for the calendar's genuinely free slots, and hands the page back a
 * plain JSON array with CORS headers. GHL stays the single source of
 * truth: change hours, block a day, take a booking, and the funnel
 * follows on the next page load.
 *
 * Deploy:  npx wrangler deploy
 * Secret:  npx wrangler secret put GHL_TOKEN
 */

const GHL_API = "https://services.leadconnectorhq.com";
const GHL_VERSION = "2021-04-15";

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }
    if (request.method !== "GET") {
      return json({ ok: false, error: "method_not_allowed" }, 405, headers);
    }

    const url = new URL(request.url);
    const debug = url.searchParams.get("debug") === "1";

    // How far ahead to ask for. GHL applies its own date range on top,
    // so asking wide costs nothing and lets GHL decide the window.
    const days = clamp(parseInt(url.searchParams.get("days") || "21", 10), 1, 60);
    const startMs = Date.now();
    const endMs = startMs + days * 86400000;

    const calendarId = env.CALENDAR_ID;
    if (!calendarId || !env.GHL_TOKEN) {
      return json({ ok: false, error: "not_configured" }, 500, headers);
    }

    const ghlUrl = new URL(`${GHL_API}/calendars/${calendarId}/free-slots`);
    ghlUrl.searchParams.set("startDate", String(startMs));
    ghlUrl.searchParams.set("endDate", String(endMs));
    if (env.TIMEZONE) ghlUrl.searchParams.set("timezone", env.TIMEZONE);

    let res;
    try {
      res = await fetch(ghlUrl.toString(), {
        headers: {
          Authorization: `Bearer ${env.GHL_TOKEN}`,
          Version: GHL_VERSION,
          Accept: "application/json"
        },
        cf: { cacheTtl: 30, cacheEverything: true }
      });
    } catch (err) {
      return json({ ok: false, error: "upstream_unreachable" }, 502, headers);
    }

    const body = await res.text();
    if (!res.ok) {
      // Surface the status so the page knows to fall back rather than
      // show an empty calendar as though nothing were available.
      return json(
        { ok: false, error: "upstream_error", status: res.status, detail: debug ? body : undefined },
        502,
        headers
      );
    }

    let data;
    try {
      data = JSON.parse(body);
    } catch (err) {
      return json({ ok: false, error: "bad_upstream_json" }, 502, headers);
    }

    const slots = extractSlots(data);

    return json(
      {
        ok: true,
        timezone: env.TIMEZONE || null,
        count: slots.length,
        slots,
        raw: debug ? data : undefined
      },
      200,
      { ...headers, "Cache-Control": "public, max-age=30" }
    );
  }
};

/**
 * GHL returns an object keyed by date, each holding a slots array:
 *   { "2026-11-13": { slots: ["2026-11-13T10:00:00-07:00", ...] },
 *     "traceId": "..." }
 * Shapes have varied across API versions, so pull any ISO-looking
 * strings out of whatever arrives rather than trusting one layout.
 */
function extractSlots(data) {
  const out = [];
  const seen = new Set();

  const take = (value) => {
    if (typeof value !== "string") return;
    const t = Date.parse(value);
    if (Number.isNaN(t) || seen.has(t)) return;
    seen.add(t);
    out.push(new Date(t).toISOString());
  };

  const walk = (node, depth) => {
    if (!node || depth > 4) return;
    if (Array.isArray(node)) { node.forEach((n) => walk(n, depth + 1)); return; }
    if (typeof node === "string") { take(node); return; }
    if (typeof node !== "object") return;
    for (const [key, value] of Object.entries(node)) {
      if (key === "traceId") continue;
      walk(value, depth + 1);
    }
  };

  walk(data, 0);
  out.sort();
  return out;
}

function corsHeaders(origin, env) {
  const allowed = (env.ALLOWED_ORIGINS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const allow = allowed.includes(origin) ? origin : allowed[0] || "*";
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin"
  };
}

function json(payload, status, headers) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...headers, "Content-Type": "application/json; charset=utf-8" }
  });
}

function clamp(n, lo, hi) {
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : lo;
}
