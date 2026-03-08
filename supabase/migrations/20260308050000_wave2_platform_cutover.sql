create extension if not exists pgcrypto;

create table if not exists public.migration_wave_state (
    key text primary key,
    value text not null,
    updated_at timestamptz not null default now()
);

create table if not exists public.app_users (
    id uuid primary key default gen_random_uuid(),
    auth_user_id uuid not null unique,
    user_name text not null unique,
    display_name text null,
    first_name text null,
    last_name text null,
    email text null,
    email_verified boolean not null default false,
    identity_provider text null,
    avatar_url text null,
    avatar_storage_path text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.app_user_roles (
    user_id uuid not null references public.app_users(id) on delete cascade,
    role text not null check (role in ('player', 'developer', 'verified_developer', 'moderator', 'admin', 'super_admin')),
    created_at timestamptz not null default now(),
    primary key (user_id, role)
);

create table if not exists public.user_board_profiles (
    user_id uuid primary key references public.app_users(id) on delete cascade,
    board_user_id text not null unique,
    display_name text null,
    avatar_url text null,
    linked_at timestamptz not null default now(),
    last_synced_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.studios (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    display_name text not null,
    description text null,
    logo_url text null,
    logo_storage_path text null,
    banner_url text null,
    banner_storage_path text null,
    created_by_user_id uuid not null references public.app_users(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.studio_memberships (
    studio_id uuid not null references public.studios(id) on delete cascade,
    user_id uuid not null references public.app_users(id) on delete cascade,
    role text not null check (role in ('owner', 'admin', 'editor')),
    joined_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (studio_id, user_id)
);

create table if not exists public.studio_links (
    id uuid primary key default gen_random_uuid(),
    studio_id uuid not null references public.studios(id) on delete cascade,
    label text not null,
    url text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.supported_publishers (
    id uuid primary key,
    key text not null unique,
    display_name text not null,
    homepage_url text not null
);

create table if not exists public.titles (
    id uuid primary key default gen_random_uuid(),
    studio_id uuid not null references public.studios(id) on delete cascade,
    slug text not null,
    content_kind text not null check (content_kind in ('game', 'app')),
    lifecycle_status text not null check (lifecycle_status in ('draft', 'testing', 'published', 'archived')),
    visibility text not null check (visibility in ('private', 'unlisted', 'listed')),
    is_reported boolean not null default false,
    current_metadata_revision integer not null default 1,
    display_name text not null,
    short_description text not null,
    description text not null,
    genre_display text not null,
    min_players integer not null,
    max_players integer not null,
    age_rating_authority text not null,
    age_rating_value text not null,
    min_age_years integer not null,
    current_release_id uuid null,
    current_release_version text null,
    current_release_published_at timestamptz null,
    acquisition_url text null,
    acquisition_label text null,
    acquisition_provider_display_name text null,
    acquisition_provider_homepage_url text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint titles_studio_slug_unique unique (studio_id, slug),
    constraint titles_player_bounds check (min_players > 0 and max_players >= min_players),
    constraint titles_draft_private check (lifecycle_status <> 'draft' or visibility = 'private')
);

create table if not exists public.title_media_assets (
    id uuid primary key default gen_random_uuid(),
    title_id uuid not null references public.titles(id) on delete cascade,
    media_role text not null check (media_role in ('card', 'hero', 'logo')),
    source_url text not null,
    storage_path text null,
    alt_text text null,
    mime_type text null,
    width integer null,
    height integer null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint title_media_assets_role_unique unique (title_id, media_role),
    constraint title_media_assets_dimensions_pair check (
        (width is null and height is null)
        or (width is not null and height is not null and width > 0 and height > 0)
    )
);

create index if not exists idx_app_users_display_name on public.app_users(display_name);
create index if not exists idx_studios_display_name on public.studios(display_name);
create index if not exists idx_titles_public_visibility on public.titles(lifecycle_status, visibility);

create or replace function public.reset_migration_demo_data()
returns void
language sql
security definer
as $$
    truncate table
        public.title_media_assets,
        public.titles,
        public.studio_links,
        public.studio_memberships,
        public.studios,
        public.user_board_profiles,
        public.app_user_roles,
        public.app_users
    restart identity cascade;
$$;

alter table public.app_users enable row level security;
alter table public.app_user_roles enable row level security;
alter table public.user_board_profiles enable row level security;
alter table public.studios enable row level security;
alter table public.studio_memberships enable row level security;
alter table public.studio_links enable row level security;
alter table public.supported_publishers enable row level security;
alter table public.titles enable row level security;
alter table public.title_media_assets enable row level security;
