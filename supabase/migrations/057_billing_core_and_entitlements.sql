-- MR Billing 01 — provider-independent billing core and entitlements
-- Paystack/Paddle identifiers belong only in provider mapping/event tables.

create extension if not exists pgcrypto;

create table if not exists billing_products (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  description text,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists billing_plans (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references billing_products(id) on delete cascade,
  code text not null,
  name text not null,
  description text,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(product_id, code)
);

create table if not exists billing_prices (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references billing_plans(id) on delete cascade,
  currency text not null check (char_length(currency)=3),
  unit_amount bigint not null check (unit_amount >= 0),
  billing_interval text not null check (billing_interval in ('one_time','month','year')),
  interval_count integer not null default 1 check (interval_count > 0),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists billing_customers (
  id uuid primary key default gen_random_uuid(),
  account_email text not null unique,
  full_name text,
  country_code text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists billing_provider_customers (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references billing_customers(id) on delete cascade,
  provider text not null,
  provider_customer_id text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(provider, provider_customer_id),
  unique(customer_id, provider)
);

create table if not exists billing_subscriptions (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references billing_customers(id) on delete cascade,
  plan_id uuid not null references billing_plans(id),
  status text not null check (status in ('pending','trialing','active','past_due','paused','cancelled','expired')),
  provider text,
  provider_subscription_id text,
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  cancelled_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, provider_subscription_id)
);

create table if not exists billing_payments (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid references billing_customers(id) on delete set null,
  subscription_id uuid references billing_subscriptions(id) on delete set null,
  price_id uuid references billing_prices(id) on delete set null,
  provider text not null,
  provider_reference text not null,
  status text not null check (status in ('initialized','pending','succeeded','failed','refunded','partially_refunded','disputed')),
  currency text not null check (char_length(currency)=3),
  amount bigint not null check (amount >= 0),
  paid_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, provider_reference)
);

create table if not exists billing_provider_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  provider_event_id text not null,
  event_type text not null,
  signature_verified boolean not null default false,
  processing_status text not null default 'received' check (processing_status in ('received','processed','ignored','failed')),
  payload jsonb not null default '{}'::jsonb,
  error_message text,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  unique(provider, provider_event_id)
);

create table if not exists billing_entitlements (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references billing_customers(id) on delete cascade,
  product_code text not null,
  feature_code text not null,
  source text not null default 'plan',
  source_subscription_id uuid references billing_subscriptions(id) on delete cascade,
  status text not null default 'active' check (status in ('active','inactive','expired','revoked')),
  limit_value numeric,
  starts_at timestamptz not null default now(),
  ends_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(customer_id, product_code, feature_code, source_subscription_id)
);

create table if not exists billing_audit_logs (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid references billing_customers(id) on delete set null,
  actor_type text not null,
  actor_reference text,
  action text not null,
  entity_type text not null,
  entity_id text,
  before_state jsonb,
  after_state jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_billing_subscriptions_customer_status on billing_subscriptions(customer_id,status);
create index if not exists idx_billing_payments_customer_created on billing_payments(customer_id,created_at desc);
create index if not exists idx_billing_entitlements_customer_status on billing_entitlements(customer_id,status);
create index if not exists idx_billing_provider_events_processing on billing_provider_events(provider,processing_status,received_at);

-- Backend/service-role only. Public clients must never mutate commercial state directly.
alter table billing_products enable row level security;
alter table billing_plans enable row level security;
alter table billing_prices enable row level security;
alter table billing_customers enable row level security;
alter table billing_provider_customers enable row level security;
alter table billing_subscriptions enable row level security;
alter table billing_payments enable row level security;
alter table billing_provider_events enable row level security;
alter table billing_entitlements enable row level security;
alter table billing_audit_logs enable row level security;

insert into billing_products(code,name,description)
values ('moveready','MoveReady','Opportunity-to-Mobility platform billing product')
on conflict (code) do update set name=excluded.name, description=excluded.description, active=true, updated_at=now();

-- Seed only the permanent free baseline now. Paid plan names/prices are intentionally not guessed.
insert into billing_plans(product_id,code,name,description,metadata)
select id,'free','Free','MoveReady launch-safe free baseline','{"commercial":false,"seeded_by":"MR_BILLING_01"}'::jsonb
from billing_products where code='moveready'
on conflict (product_id,code) do update set name=excluded.name, description=excluded.description, active=true, metadata=excluded.metadata, updated_at=now();
