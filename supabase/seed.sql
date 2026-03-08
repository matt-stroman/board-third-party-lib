insert into public.migration_wave_state(key, value)
values
    ('wave', 'wave-2'),
    ('status', 'platform-api-ready')
on conflict (key) do update
set value = excluded.value,
    updated_at = now();

insert into public.supported_publishers(id, key, display_name, homepage_url)
values
    ('44444444-4444-4444-4444-444444444444', 'itch-io', 'itch.io', 'https://itch.io/'),
    ('55555555-5555-5555-5555-555555555555', 'humble-bundle', 'Humble Bundle', 'https://www.humblebundle.com/'),
    ('12121212-1212-1212-1212-121212121212', 'custom-direct', 'Direct Publisher', 'https://publishers.boardenthusiasts.dev/')
on conflict (id) do update
set key = excluded.key,
    display_name = excluded.display_name,
    homepage_url = excluded.homepage_url;
