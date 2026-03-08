-- Wave 1 seed placeholder.
-- Wave 2 will replace this with relational demo data, auth fixtures, and storage metadata.

create table if not exists public.migration_wave_state (
    key text primary key,
    value text not null,
    updated_at timestamptz not null default now()
);

insert into public.migration_wave_state(key, value)
values
    ('wave', 'wave-1'),
    ('status', 'foundation-ready')
on conflict (key) do update
set value = excluded.value,
    updated_at = now();
