// ============================================================
// POST /functions/v1/validate-license
//
// Called directly by the EA running inside MetaTrader 5.
// Unauthenticated — the licence key is the credential.
//
// Deploy:  supabase functions deploy validate-license --no-verify-jwt
// Secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, LICENSE_HMAC_SECRET
// ============================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const HMAC_SECRET = Deno.env.get("LICENSE_HMAC_SECRET")!;

const RATE_LIMIT_PER_HOUR = 30;

type Result =
  | "valid"
  | "wrong_product"
  | "invalid_key"
  | "expired"
  | "not_bound"
  | "not_affiliate"
  | "slot_exceeded"
  | "revoked"
  | "maintenance";

// ------------------------------------------------------------
// Sign the response so the EA can prove it came from us.
// Prevents a spoofed local server or edited hosts file from
// faking a "valid" reply.
// ------------------------------------------------------------
async function sign(payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(HMAC_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(payload),
  );
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function respond(
  result: Result,
  key: string,
  account: string,
  extra: Record<string, unknown> = {},
  nonce = "",
  httpStatus = 200,
) {
  const valid = result === "valid";
  const serverTime = new Date().toISOString();

  // Signed over the fields that matter. Order is fixed and the EA
  // must reconstruct it identically.
  const signature = await sign(
    `${key}|${account}|${valid}|${serverTime}|${nonce}`,
  );

  const body = {
    valid,
    result,
    message: messageFor(result),
    server_time: serverTime,
    nonce,
    signature,
    ...extra,
  };

  return new Response(JSON.stringify(body), {
    status: httpStatus,
    headers: { "Content-Type": "application/json" },
  });
}

// Deliberately generic. Granular reasons live in the log, not in
// the reply — we don't confirm to an attacker which keys exist.
function messageFor(r: Result): string {
  switch (r) {
    case "valid":
      return "Licence active";
    case "not_bound":
      return "This account is not linked to your licence. Add it in your dashboard.";
    case "not_affiliate":
      return "This account is not registered under our partner link.";
    case "slot_exceeded":
      return "Account limit reached for this licence.";
    case "expired":
      return "Licence expired.";
    case "revoked":
      return "Licence suspended. Contact support.";
    case "maintenance":
      return "Validation temporarily unavailable.";
    default:
      return "Licence not recognised.";
  }
}

async function log(
  key: string,
  account: string,
  result: Result,
  req: Request,
  eaVersion?: string,
  terminalId?: string,
) {
  await supabase.from("validation_log").insert({
    license_key: key,
    account_number: account,
    result,
    ea_version: eaVersion ?? null,
    terminal_id: terminalId ?? null,
    ip: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
  });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  let payload: {
    key?: string;
    account?: string;
    product?: string;      // product code, e.g. MILLIONAIRE_SCALPER | CYNERA
    ea_version?: string;
    terminal_id?: string;
    nonce?: string;
  };

  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ valid: false, message: "Bad request" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const key = (payload.key ?? "").trim().toUpperCase();
  const account = (payload.account ?? "").trim();
  const nonce = (payload.nonce ?? "").slice(0, 64);

  if (!key || !account) {
    return respond("invalid_key", key, account, {}, nonce);
  }

  // --- Maintenance mode -------------------------------------
  const { data: settings } = await supabase
    .from("settings")
    .select("*")
    .eq("id", 1)
    .single();

  if (settings?.maintenance_mode) {
    // IMPORTANT: not a failure. The EA should treat this as
    // "unknown" and keep running on its cached grace period.
    return respond("maintenance", key, account, {}, nonce, 503);
  }

  // --- Rate limit -------------------------------------------
  const oneHourAgo = new Date(Date.now() - 3600_000).toISOString();
  const { count } = await supabase
    .from("validation_log")
    .select("id", { count: "exact", head: true })
    .eq("license_key", key)
    .gte("created_at", oneHourAgo);

  if ((count ?? 0) > RATE_LIMIT_PER_HOUR) {
    // 429, not "invalid". The EA must not stop trading because
    // it checked in too often.
    return new Response(
      JSON.stringify({
        valid: false,
        result: "rate_limited",
        message: "Too many checks. Retry later.",
        retry_after: 3600,
      }),
      { status: 429, headers: { "Content-Type": "application/json" } },
    );
  }

  // --- 1. Key exists and is active --------------------------
  const { data: licence } = await supabase
    .from("licenses")
    .select(
      "id, tier, max_slots, affiliate_locked, status, expires_at, product_id, products(code, broker, model)",
    )
    .eq("license_key", key)
    .maybeSingle();

  if (!licence) {
    await log(key, account, "invalid_key", req, payload.ea_version, payload.terminal_id);
    return respond("invalid_key", key, account, {}, nonce);
  }

  if (licence.status !== "active") {
    await log(key, account, "revoked", req, payload.ea_version, payload.terminal_id);
    return respond("revoked", key, account, {}, nonce);
  }

  // --- 1b. Licence matches the product asking ---------------
  // Stops a Monarchal key being used to run Cynera.
  const product = (licence as any).products;
  const requested = (payload.product ?? "").trim().toUpperCase();
  if (requested && product?.code && requested !== product.code) {
    await log(key, account, "wrong_product", req, payload.ea_version, payload.terminal_id);
    return respond("invalid_key", key, account, {}, nonce);
  }

  // --- 2. Not expired ---------------------------------------
  if (licence.expires_at && new Date(licence.expires_at) < new Date()) {
    await log(key, account, "expired", req, payload.ea_version, payload.terminal_id);
    return respond("expired", key, account, {}, nonce);
  }

  // --- 3. Account is actively bound to this key -------------
  const { data: binding } = await supabase
    .from("license_bindings")
    .select("id")
    .eq("license_id", licence.id)
    .eq("account_number", account)
    .eq("is_active", true)
    .maybeSingle();

  if (!binding) {
    await log(key, account, "not_bound", req, payload.ea_version, payload.terminal_id);
    return respond("not_bound", key, account, {}, nonce);
  }

  // --- 4. Affiliate gate ------------------------------------
  // Only applies to AFFILIATE-model products. DIRECT products
  // (Cynera, Vertex Signals) were paid for outright and run on
  // any account, including prop firm accounts we never referred.
  const isDirect = product?.model === "DIRECT";

  const mustCheckAffiliate =
    !isDirect &&
    licence.affiliate_locked &&
    (licence.tier !== "LIFETIME" || settings?.lifetime_requires_affiliate);

  if (mustCheckAffiliate) {
    // Route to the right broker table for this product.
    const table = product?.broker === "DERIV" ? "deriv_clients" : "exness_clients";

    const { data: client } = await supabase
      .from(table)
      .select("is_under_affiliate")
      .eq("account_number", account)
      .maybeSingle();

    if (!client?.is_under_affiliate) {
      await log(key, account, "not_affiliate", req, payload.ea_version, payload.terminal_id);
      return respond("not_affiliate", key, account, {}, nonce);
    }
  }

  // --- 5. Slot ceiling --------------------------------------
  if (licence.max_slots !== null) {
    const { count: used } = await supabase
      .from("license_bindings")
      .select("id", { count: "exact", head: true })
      .eq("license_id", licence.id)
      .eq("is_active", true);

    if ((used ?? 0) > licence.max_slots) {
      await log(key, account, "slot_exceeded", req, payload.ea_version, payload.terminal_id);
      return respond("slot_exceeded", key, account, {}, nonce);
    }
  }

  // --- Valid -------------------------------------------------
  await log(key, account, "valid", req, payload.ea_version, payload.terminal_id);

  return respond(
    "valid",
    key,
    account,
    {
      tier: licence.tier,
      product: product?.code ?? null,
      expires_at: licence.expires_at,
      recheck_hours: settings?.validation_cache_hours ?? 6,
      grace_hours: settings?.grace_period_hours ?? 72,
    },
    nonce,
  );
});
