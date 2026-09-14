-- ============================================================
-- VERTEX Millionaire Scalper — Platform Schema v2
-- KIMAIGA · VERTEX AI
-- Adds: live account transparency, referral programme
-- ============================================================

create extension if not exists "pgcrypto";

-- ------------------------------------------------------------
-- PROFILES
-- ------------------------------------------------------------
create table profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  email        text not null,
  full_name    text,
  country      text,
  phone        text,
  role         text not null default 'user' check (role in ('user','admin')),
  referred_by  uuid references profiles(id),
  created_at   timestamptz not null default now()
);

-- ------------------------------------------------------------
-- EXNESS CLIENTS — synced from the Partnership API.
-- total_volume_lots and first_trade_at drive referral rewards.
-- ------------------------------------------------------------
create table exness_clients (
  id                 uuid primary key default gen_random_uuid(),
  account_number     text unique not null,
  client_uid         text,
  account_type       text,
  registered_at      timestamptz,
  is_under_affiliate boolean not null default true,
  total_volume_lots  numeric(16,4) not null default 0,
  first_trade_at     timestamptz,
  last_deposit_at    timestamptz,
  total_deposits_usd numeric(14,2) default 0,
  verified_manually  boolean not null default false,
  verified_by        uuid references profiles(id),
  last_synced_at     timestamptz default now(),
  raw                jsonb
);

create index on exness_clients (client_uid);
create index on exness_clients (is_under_affiliate);

-- ------------------------------------------------------------
-- PRODUCTS — VERTEX AI is a multi-product platform.
-- Millionaire Scalper is the first; more will follow.
-- ------------------------------------------------------------
create table products (
  id            uuid primary key default gen_random_uuid(),
  code          text unique not null,          -- 'MILLIONAIRE_SCALPER'
  name          text not null,
  slug          text unique not null,
  tagline       text,                          -- 'XAUUSD · MT5 · Grid scalper'
  description   text,
  status        text not null default 'development'
                check (status in ('development','beta','live','retired')),
  platform      text not null default 'MT5'
                check (platform in ('MT5','MT4','DERIV','TRADINGVIEW')),
  broker        text                              -- 'EXNESS' | 'DERIV' | null (any / none)
                check (broker in ('EXNESS','DERIV') or broker is null),
  model         text not null default 'AFFILIATE' -- how it is monetised
                check (model in ('AFFILIATE','DIRECT')),
  risk_level    text default 'medium' check (risk_level in ('low','medium','high','very_high')),
  direct_price_usd numeric(10,2),
  current_version text,
  file_url      text,                          -- .ex5 in Supabase Storage
  changelog     text,
  display_order int not null default 0,
  created_at    timestamptz not null default now()
);

-- FREE (affiliate): unlocked by verifying an Exness account under our link.
-- PREMIUM (direct):  one-time purchase, no partner account required.
insert into products (code,name,slug,tagline,status,platform,broker,model,risk_level,direct_price_usd,current_version,display_order) values
 ('MILLIONAIRE_SCALPER','Millionaire Scalper','millionaire-scalper','XAUUSD · Grid scalper',
  'live','MT5','EXNESS','AFFILIATE','high',599,'1.00',0),
 ('VERTEX_SIGNALS','Vertex Signals','vertex-signals','Entry · SL · TP1–TP3',
  'live','TRADINGVIEW','EXNESS','AFFILIATE','low',null,'1.00',1),
 ('VERTEX_DOMINION','Vertex Dominion','vertex-dominion','All FX pairs · Multi-currency',
  'live','MT4',null,'DIRECT','medium',149,'1.00',2),
 ('VERTEX_CITADEL','Vertex Citadel','vertex-citadel','Prop firm ready',
  'live','MT4',null,'DIRECT','medium',299,'1.00',3),
 ('VERTEX_SNIPER','Vertex Sniper','vertex-sniper','Volatility 100 (1s) · Digits',
  'live','DERIV',null,'DIRECT','very_high',15,'2.00',4);


-- ------------------------------------------------------------
-- DERIV CLIENTS — synced from the Deriv partner/affiliate API.
-- Vertex Sniper verifies against this table, not exness_clients.
-- ------------------------------------------------------------
create table deriv_clients (
  id                 uuid primary key default gen_random_uuid(),
  account_number     text unique not null,      -- CR######## loginid
  client_uid         text,
  currency           text,
  registered_at      timestamptz,
  is_under_affiliate boolean not null default true,
  total_turnover_usd numeric(16,2) not null default 0,
  first_trade_at     timestamptz,
  total_deposits_usd numeric(14,2) default 0,
  verified_manually  boolean not null default false,
  verified_by        uuid references profiles(id),
  last_synced_at     timestamptz default now(),
  raw                jsonb
);

create index on deriv_clients (client_uid);
create index on deriv_clients (is_under_affiliate);

-- Unified verification view — the licence wizard queries this,
-- so it does not need to know which broker a product uses.
create or replace view verified_accounts as
  select account_number, client_uid, account_type, 'EXNESS'::text as broker,
         is_under_affiliate, total_volume_lots as volume, first_trade_at,
         total_deposits_usd, registered_at
    from exness_clients
  union all
  select account_number, client_uid, currency, 'DERIV'::text,
         is_under_affiliate, total_turnover_usd, first_trade_at,
         total_deposits_usd, registered_at
    from deriv_clients;

-- ------------------------------------------------------------
-- LICENSES
-- ------------------------------------------------------------
create table licenses (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references profiles(id) on delete cascade,
  product_id           uuid not null references products(id),
  license_key          text unique not null,
  tier                 text not null check (tier in ('FREE','SLOT_1','SLOT_6','LIFETIME','SOURCE')),
  max_slots            int,                    -- null = unlimited
  affiliate_locked     boolean not null default true,
  status               text not null default 'active'
                       check (status in ('active','suspended','revoked')),
  anchor_client_uid    text,
  binding_changes_used int not null default 0,
  referral_slots       int not null default 0, -- slots earned via referrals
  issued_at            timestamptz not null default now(),
  expires_at           timestamptz,
  notes                text
);

create index on licenses (user_id);

-- HARD RULE: one FREE licence per Exness client PER PRODUCT, forever.
create unique index one_free_license_per_client_product
  on licenses (anchor_client_uid, product_id)
  where tier = 'FREE' and anchor_client_uid is not null;

-- ------------------------------------------------------------
-- BINDINGS
-- ------------------------------------------------------------
create table license_bindings (
  id             uuid primary key default gen_random_uuid(),
  license_id     uuid not null references licenses(id) on delete cascade,
  account_number text not null,
  broker         text check (broker in ('EXNESS','DERIV') or broker is null),
  is_active      boolean not null default true,
  bound_at       timestamptz not null default now(),
  unbound_at     timestamptz
);

-- One active binding per account PER PRODUCT (an account may run
-- Millionaire Scalper and Monarchal simultaneously).
create unique index one_active_binding_per_account_product
  on license_bindings (account_number, license_id) where is_active;

create table binding_changes (
  id          bigserial primary key,
  license_id  uuid not null references licenses(id) on delete cascade,
  old_account text,
  new_account text,
  changed_by  uuid references profiles(id),
  changed_at  timestamptz not null default now(),
  ip          inet,
  reason      text
);

-- ============================================================
-- LIVE ACCOUNT TRANSPARENCY
-- The investor password is READ-ONLY and intended to be public,
-- but is stored encrypted so it never sits in plain text.
-- ============================================================
create table live_accounts (
  id                    uuid primary key default gen_random_uuid(),
  label                 text not null,          -- "Cent Account — Conservative"
  broker                text not null default 'Exness',
  server                text not null,          -- "Exness-MT5Real8"
  account_number        text not null,
  investor_password_enc bytea not null,         -- pgp_sym_encrypt
  platform              text not null default 'MetaTrader 5',
  strategy_note         text,
  myfxbook_url          text,
  fxblue_url            text,
  is_public             boolean not null default false,
  display_order         int not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create table live_account_stats (
  account_id            uuid primary key references live_accounts(id) on delete cascade,
  balance               numeric(14,2),
  equity                numeric(14,2),
  gain_pct              numeric(8,2),
  max_drawdown_pct      numeric(8,2),
  total_trades          int,
  win_rate_pct          numeric(6,2),
  profit_factor         numeric(8,2),
  currently_in_drawdown boolean default false,
  updated_at            timestamptz not null default now()
);

-- Helpers for the encrypted investor password.
-- Store the key as a Supabase secret; pass it in from the Edge Function.
create or replace function set_investor_password(
  p_account_id uuid, p_password text, p_key text
) returns void language sql security definer as $$
  update live_accounts
     set investor_password_enc = pgp_sym_encrypt(p_password, p_key),
         updated_at = now()
   where id = p_account_id;
$$;

create or replace function get_investor_password(
  p_account_id uuid, p_key text
) returns text language sql security definer stable as $$
  select pgp_sym_decrypt(investor_password_enc, p_key)
    from live_accounts where id = p_account_id;
$$;

-- ============================================================
-- REFERRAL PROGRAMME
-- Reward = +1 account slot, granted only after the referred
-- trader has funded AND actually traded.
-- ============================================================
create table referral_codes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references profiles(id) on delete cascade,
  code       text unique not null,
  is_active  boolean not null default true,
  created_at timestamptz not null default now()
);

create index on referral_codes (user_id);

create table referrals (
  id                     uuid primary key default gen_random_uuid(),
  referrer_user_id       uuid not null references profiles(id) on delete cascade,
  referred_user_id       uuid references profiles(id),
  referred_account_number text,
  code_used              text,

  status text not null default 'clicked' check (status in (
    'clicked','registered','account_opened','verified',
    'funded','trading','qualified','rewarded','blocked'
  )),

  clicked_at        timestamptz default now(),
  registered_at     timestamptz,
  account_opened_at timestamptz,
  verified_at       timestamptz,
  funded_at         timestamptz,
  first_trade_at    timestamptz,
  qualified_at      timestamptz,   -- entered holding period
  rewarded_at       timestamptz,   -- slot actually granted

  reward_slots   int not null default 1,
  blocked_reason text,
  device_hash    text,
  created_at     timestamptz not null default now()
);

create index on referrals (referrer_user_id, status);
create index on referrals (status);

-- A referred account can only ever be rewarded once, across all referrers.
create unique index one_reward_per_referred_account
  on referrals (referred_account_number)
  where referred_account_number is not null;

create table referral_events (
  id          bigserial primary key,
  referral_id uuid not null references referrals(id) on delete cascade,
  from_status text,
  to_status   text not null,
  note        text,
  created_at  timestamptz not null default now()
);

create table referral_rewards (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references profiles(id) on delete cascade,
  referral_id   uuid not null references referrals(id) on delete cascade,
  slots_granted int not null default 1,
  granted_at    timestamptz not null default now(),
  reversed_at   timestamptz,
  note          text
);

create index on referral_rewards (user_id);

-- ------------------------------------------------------------
-- ORDERS / SOURCE REQUESTS / LOGS / SETTINGS
-- ------------------------------------------------------------
create table orders (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references profiles(id),
  package_code       text not null,
  amount_usd         numeric(10,2) not null,
  currency           text not null default 'USD',
  provider           text,
  provider_reference text,
  status             text not null default 'pending'
                     check (status in ('pending','paid','failed','refunded')),
  created_at         timestamptz not null default now(),
  paid_at            timestamptz
);

create table source_requests (
  id         uuid primary key default gen_random_uuid(),
  full_name  text not null,
  email      text not null,
  phone      text,
  company    text,
  message    text,
  status     text not null default 'new'
             check (status in ('new','contacted','negotiating','closed_won','closed_lost')),
  created_at timestamptz not null default now()
);

create table validation_log (
  id             bigserial primary key,
  license_key    text,
  account_number text,
  ip             inet,
  ea_version     text,
  terminal_id    text,
  result         text not null,
  created_at     timestamptz not null default now()
);

create index on validation_log (license_key, created_at desc);
create index on validation_log (account_number, created_at desc);

create table settings (
  id                          int primary key default 1 check (id = 1),
  lifetime_requires_affiliate boolean not null default true,
  free_binding_change_limit   int not null default 3,
  validation_cache_hours      int not null default 6,
  grace_period_hours          int not null default 72,
  maintenance_mode            boolean not null default false,
  affiliate_link              text,
  referral_min_deposit        numeric(10,2) not null default 100,
  referral_holding_days       int not null default 7,
  referral_max_slots_per_user int not null default 50
);

insert into settings (id) values (1) on conflict do nothing;

create table admin_audit (
  id          bigserial primary key,
  admin_id    uuid references profiles(id),
  action      text not null,
  target_type text,
  target_id   text,
  meta        jsonb,
  created_at  timestamptz not null default now()
);

-- ============================================================
-- REFERRAL QUALIFICATION ENGINE
-- Run after each Exness sync.
-- ============================================================
create or replace function advance_referral(p_referral_id uuid, p_to text, p_note text default null)
returns void language plpgsql as $$
declare v_from text;
begin
  select status into v_from from referrals where id = p_referral_id;
  if v_from is distinct from p_to then
    update referrals set status = p_to,
      verified_at    = case when p_to='verified'   then coalesce(verified_at,now())    else verified_at end,
      funded_at      = case when p_to='funded'     then coalesce(funded_at,now())      else funded_at end,
      first_trade_at = case when p_to='trading'    then coalesce(first_trade_at,now()) else first_trade_at end,
      qualified_at   = case when p_to='qualified'  then coalesce(qualified_at,now())   else qualified_at end,
      rewarded_at    = case when p_to='rewarded'   then coalesce(rewarded_at,now())    else rewarded_at end
    where id = p_referral_id;

    insert into referral_events (referral_id, from_status, to_status, note)
    values (p_referral_id, v_from, p_to, p_note);
  end if;
end;
$$;

-- Move referrals forward based on the latest Exness data.
create or replace function process_referrals() returns int
language plpgsql as $$
declare
  r          record;
  s          settings%rowtype;
  moved      int := 0;
  v_slots    int;
begin
  select * into s from settings where id = 1;

  for r in
    select rf.*, ec.is_under_affiliate, ec.total_volume_lots,
           ec.total_deposits_usd, ec.first_trade_at as ec_first_trade
      from referrals rf
      join exness_clients ec on ec.account_number = rf.referred_account_number
     where rf.status not in ('rewarded','blocked')
  loop
    -- verified under our affiliate
    if r.is_under_affiliate and r.status in ('clicked','registered','account_opened') then
      perform advance_referral(r.id, 'verified');
      moved := moved + 1;
    end if;

    -- funded to threshold
    if r.is_under_affiliate
       and coalesce(r.total_deposits_usd,0) >= s.referral_min_deposit
       and r.status = 'verified' then
      perform advance_referral(r.id, 'funded');
      moved := moved + 1;
    end if;

    -- actually traded — the anti-abuse gate
    if coalesce(r.total_volume_lots,0) > 0
       and r.ec_first_trade is not null
       and r.status = 'funded' then
      perform advance_referral(r.id, 'trading');
      perform advance_referral(r.id, 'qualified', 'entered holding period');
      moved := moved + 1;
    end if;

    -- holding period elapsed -> grant the slot
    if r.status = 'qualified'
       and r.qualified_at is not null
       and now() >= r.qualified_at + (s.referral_holding_days || ' days')::interval then

      select coalesce(sum(slots_granted),0) into v_slots
        from referral_rewards
       where user_id = r.referrer_user_id and reversed_at is null;

      if v_slots < s.referral_max_slots_per_user then
        insert into referral_rewards (user_id, referral_id, slots_granted)
        values (r.referrer_user_id, r.id, r.reward_slots);

        update licenses
           set referral_slots = referral_slots + r.reward_slots,
               max_slots = case when max_slots is null
                                then null
                                else max_slots + r.reward_slots end
         where user_id = r.referrer_user_id
           and status = 'active'
           and tier <> 'SOURCE';

        perform advance_referral(r.id, 'rewarded', 'slot granted');
        moved := moved + 1;
      else
        update referrals set status = 'blocked',
               blocked_reason = 'referral slot cap reached'
         where id = r.id;
      end if;
    end if;
  end loop;

  return moved;
end;
$$;

-- Self-referral guard
create or replace function block_self_referral() returns trigger
language plpgsql as $$
declare v_same boolean;
begin
  select exists (
    select 1
      from license_bindings lb
      join licenses l on l.id = lb.license_id
     where l.user_id = new.referrer_user_id
       and lb.account_number = new.referred_account_number
       and lb.is_active
  ) into v_same;

  if v_same then
    new.status := 'blocked';
    new.blocked_reason := 'self-referral: account already bound to referrer';
  end if;
  return new;
end;
$$;

create trigger trg_block_self_referral
  before insert or update of referred_account_number on referrals
  for each row execute function block_self_referral();

-- ============================================================
-- HELPERS
-- ============================================================
create or replace function generate_license_key() returns text
language plpgsql as $$
declare
  alphabet text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  block text; result text := 'VMS'; i int; j int;
begin
  for i in 1..4 loop
    block := '';
    for j in 1..4 loop
      block := block || substr(alphabet, 1 + floor(random()*length(alphabet))::int, 1);
    end loop;
    result := result || '-' || block;
  end loop;
  return result;
end;
$$;

create or replace function generate_referral_code() returns text
language plpgsql as $$
declare
  alphabet text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  result text := ''; i int;
begin
  for i in 1..6 loop
    result := result || substr(alphabet, 1 + floor(random()*length(alphabet))::int, 1);
  end loop;
  return result;
end;
$$;

create or replace function active_binding_count(p_license_id uuid) returns int
language sql stable as $$
  select count(*)::int from license_bindings
   where license_id = p_license_id and is_active;
$$;

create or replace function has_free_slot(p_license_id uuid) returns boolean
language plpgsql stable as $$
declare v_max int; v_used int;
begin
  select max_slots into v_max from licenses where id = p_license_id;
  if v_max is null then return true; end if;
  select active_binding_count(p_license_id) into v_used;
  return v_used < v_max;
end;
$$;

create or replace function prune_validation_log() returns void
language sql as $$
  delete from validation_log where created_at < now() - interval '90 days';
$$;


-- ============================================================
-- MANAGED SETUP (VPS) — for clients without a computer
--
-- IMPORTANT: this service is SETUP AND CONFIGURATION ASSISTANCE.
-- The client's broker account remains in their name, funds stay
-- with the broker, and access is revocable by password change.
-- VERTEX AI never takes custody of client funds. Do not model
-- this as discretionary account management.
-- ============================================================
create table service_bookings (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references profiles(id) on delete set null,
  full_name       text not null,
  email           text not null,
  phone           text,
  country         text,
  timezone        text,
  preferred_slot  timestamptz,
  account_number  text,
  has_own_device  boolean default false,
  notes           text,
  status          text not null default 'requested' check (status in (
                    'requested','scheduled','completed','no_show','cancelled')),
  assistant_id    uuid references profiles(id),
  scheduled_at    timestamptz,
  completed_at    timestamptz,
  created_at      timestamptz not null default now()
);

create index on service_bookings (status, created_at desc);

create table managed_services (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references profiles(id) on delete cascade,
  booking_id         uuid references service_bookings(id),
  account_number     text not null,
  vps_provider       text,
  vps_region         text,
  monthly_fee_usd    numeric(8,2) not null default 30,
  exness_free_vps    boolean not null default false,  -- qualified for broker's free VPS
  consent_given_at   timestamptz,                     -- explicit written authorisation
  consent_text       text,                            -- snapshot of what they agreed to
  access_revoked_at  timestamptz,
  status             text not null default 'pending' check (status in (
                       'pending','active','paused','ended')),
  started_at         timestamptz,
  ended_at           timestamptz,
  notes              text,
  created_at         timestamptz not null default now()
);

create index on managed_services (user_id, status);

-- Every action taken on a managed account must be logged.
-- This protects the client and protects you.
create table managed_service_log (
  id         bigserial primary key,
  service_id uuid not null references managed_services(id) on delete cascade,
  actor_id   uuid references profiles(id),
  action     text not null,      -- 'vps_configured','ea_installed','ea_restarted','settings_changed'
  detail     text,
  created_at timestamptz not null default now()
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
alter table profiles          enable row level security;
alter table licenses          enable row level security;
alter table license_bindings  enable row level security;
alter table binding_changes   enable row level security;
alter table orders            enable row level security;
alter table exness_clients    enable row level security;
alter table validation_log    enable row level security;
alter table source_requests   enable row level security;
alter table settings          enable row level security;
alter table admin_audit       enable row level security;
alter table live_accounts     enable row level security;
alter table live_account_stats enable row level security;
alter table referral_codes    enable row level security;
alter table referrals         enable row level security;
alter table referral_events   enable row level security;
alter table referral_rewards  enable row level security;
alter table products            enable row level security;
alter table service_bookings    enable row level security;
alter table managed_services    enable row level security;
alter table managed_service_log enable row level security;
alter table deriv_clients       enable row level security;

create or replace function is_admin() returns boolean
language sql security definer stable as $$
  select exists (select 1 from profiles where id = auth.uid() and role = 'admin');
$$;

create policy "read own profile"   on profiles for select using (id = auth.uid() or is_admin());
create policy "update own profile" on profiles for update using (id = auth.uid());

create policy "read own licences" on licenses
  for select using (user_id = auth.uid() or is_admin());

create policy "read own bindings" on license_bindings
  for select using (is_admin() or exists (
    select 1 from licenses l where l.id = license_bindings.license_id and l.user_id = auth.uid()));

create policy "read own binding history" on binding_changes
  for select using (is_admin() or exists (
    select 1 from licenses l where l.id = binding_changes.license_id and l.user_id = auth.uid()));

create policy "read own orders" on orders
  for select using (user_id = auth.uid() or is_admin());

-- Referrals: a user sees only referrals they made
create policy "read own referral code" on referral_codes
  for select using (user_id = auth.uid() or is_admin());
create policy "read own referrals" on referrals
  for select using (referrer_user_id = auth.uid() or is_admin());
create policy "read own rewards" on referral_rewards
  for select using (user_id = auth.uid() or is_admin());
create policy "admin reads referral events" on referral_events
  for select using (is_admin());

-- Live accounts are PUBLIC when published — but never expose the
-- encrypted password column to the browser. Serve the decrypted
-- password only through an Edge Function reading published rows.
create policy "anyone reads published accounts" on live_accounts
  for select using (is_public = true or is_admin());
create policy "anyone reads published stats" on live_account_stats
  for select using (exists (
    select 1 from live_accounts la
     where la.id = live_account_stats.account_id and (la.is_public or is_admin())));

-- Products are public
create policy "anyone reads live products" on products
  for select using (status in ('live','beta') or is_admin());

-- Bookings: anyone may request; users see their own
create policy "anyone books a call" on service_bookings
  for insert with check (true);
create policy "read own bookings" on service_bookings
  for select using (user_id = auth.uid() or is_admin());

create policy "read own managed service" on managed_services
  for select using (user_id = auth.uid() or is_admin());
create policy "admin reads service log" on managed_service_log
  for select using (is_admin());

create policy "admin reads clients"     on exness_clients  for select using (is_admin());
create policy "admin reads deriv"      on deriv_clients   for select using (is_admin());
create policy "admin reads validations" on validation_log  for select using (is_admin());
create policy "admin reads requests"    on source_requests for select using (is_admin());
create policy "admin reads audit"       on admin_audit     for select using (is_admin());
create policy "anyone submits request"  on source_requests for insert with check (true);
create policy "read settings"           on settings for select using (auth.role() = 'authenticated');
create policy "admin writes settings"   on settings for update using (is_admin());
