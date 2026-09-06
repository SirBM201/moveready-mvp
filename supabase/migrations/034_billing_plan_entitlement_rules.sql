-- MR Billing 03 — plan entitlement rules and safe synchronization

create table if not exists billing_plan_entitlements (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references billing_plans(id) on delete cascade,
  product_code text not null,
  feature_code text not null,
  limit_value numeric,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(plan_id, product_code, feature_code)
);

create index if not exists idx_billing_plan_entitlements_plan_active
  on billing_plan_entitlements(plan_id, active);

alter table billing_plan_entitlements enable row level security;

-- Rebuild only plan-derived entitlements for one subscription. Manual/admin grants
-- remain untouched. Active/trialing subscriptions grant access; all other states revoke it.
create or replace function billing_sync_subscription_entitlements(p_subscription_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_subscription billing_subscriptions%rowtype;
begin
  select * into v_subscription
  from billing_subscriptions
  where id = p_subscription_id;

  if not found then
    raise exception 'billing_subscription_not_found';
  end if;

  delete from billing_entitlements
  where source = 'plan'
    and source_subscription_id = p_subscription_id;

  if v_subscription.status in ('active','trialing') then
    insert into billing_entitlements(
      customer_id, product_code, feature_code, source,
      source_subscription_id, status, limit_value, starts_at, ends_at, metadata
    )
    select
      v_subscription.customer_id,
      rule.product_code,
      rule.feature_code,
      'plan',
      v_subscription.id,
      'active',
      rule.limit_value,
      coalesce(v_subscription.current_period_start, now()),
      v_subscription.current_period_end,
      jsonb_build_object('plan_id', v_subscription.plan_id, 'sync','billing_sync_subscription_entitlements')
    from billing_plan_entitlements rule
    where rule.plan_id = v_subscription.plan_id
      and rule.active = true;
  end if;
end;
$$;

create or replace function billing_subscription_entitlement_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform billing_sync_subscription_entitlements(new.id);
  return new;
end;
$$;

drop trigger if exists trg_billing_subscription_entitlements on billing_subscriptions;
create trigger trg_billing_subscription_entitlements
after insert or update of status, plan_id, current_period_start, current_period_end
on billing_subscriptions
for each row execute function billing_subscription_entitlement_trigger();

-- Free is an explicit baseline, not a paid entitlement. Feature rules are intentionally
-- conservative until the final MoveReady commercial limits are approved.
insert into billing_plan_entitlements(plan_id, product_code, feature_code, limit_value, metadata)
select p.id, 'moveready', x.feature_code, x.limit_value, '{"baseline":true,"seeded_by":"MR_BILLING_03"}'::jsonb
from billing_plans p
join billing_products product on product.id = p.product_id and product.code = 'moveready'
cross join (values
  ('account_access'::text, null::numeric),
  ('opportunity_browse'::text, null::numeric)
) as x(feature_code, limit_value)
where p.code = 'free'
on conflict (plan_id, product_code, feature_code)
do update set active=true, limit_value=excluded.limit_value, metadata=excluded.metadata, updated_at=now();
