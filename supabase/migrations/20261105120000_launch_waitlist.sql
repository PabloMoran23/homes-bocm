-- One-off launch notification requests, separate from analytics and newsletters.
create table if not exists public.homes_launch_waitlist (
  email text not null check (length(email) between 3 and 254 and email = lower(trim(email))),
  source text not null check (source in ('project', 'boletin', 'dashboard')),
  context_key text not null default '' check (length(context_key) <= 200),
  consent_version text not null,
  created_at timestamptz not null default now(),
  primary key (email, source, context_key)
);

alter table public.homes_launch_waitlist enable row level security;
revoke all on table public.homes_launch_waitlist from anon, authenticated;
grant select, insert on table public.homes_launch_waitlist to service_role;

comment on table public.homes_launch_waitlist is
  'Emails requested solely for the Homes alerts launch notice. Not a newsletter subscription.';

-- A server-only key authorizes this one insert operation, without a service-role key.
create table if not exists public.homes_launch_waitlist_config (
  singleton boolean primary key default true check (singleton),
  key_hash text not null
);
alter table public.homes_launch_waitlist_config enable row level security;
revoke all on table public.homes_launch_waitlist_config from anon, authenticated;

create or replace function public.homes_launch_waitlist_register(
  p_key text, p_email text, p_source text, p_context_key text default ''
) returns void language plpgsql security definer set search_path = '' as $$
begin
  if not exists (
    select 1 from public.homes_launch_waitlist_config
    where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')
  ) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;
  if p_email is null or length(p_email) > 254
     or p_email <> lower(trim(p_email)) or p_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
     or p_source is null or p_source not in ('project', 'boletin', 'dashboard')
     or p_context_key is null or length(p_context_key) > 200
     or (p_source = 'project' and length(trim(p_context_key)) = 0)
     or (p_source <> 'project' and p_context_key <> '') then
    raise exception 'Invalid request' using errcode = '22023';
  end if;
  insert into public.homes_launch_waitlist (email, source, context_key, consent_version)
    values (p_email, p_source, p_context_key, 'launch-notice-' || p_source || '-v1')
    on conflict (email, source, context_key) do nothing;
end $$;
revoke all on function public.homes_launch_waitlist_register(text, text, text, text) from public;
grant execute on function public.homes_launch_waitlist_register(text, text, text, text) to anon, authenticated, service_role;
