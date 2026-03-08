import { readFile } from "node:fs/promises";
import path from "node:path";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  migrationMediaBucket,
  migrationSeedStudios,
  migrationSeedTitles,
  migrationSeedUsers
} from "../packages/migration-contract/src/index";

interface SeedOptions {
  supabaseUrl: string;
  serviceRoleKey: string;
  password: string;
  assetRoot: string;
  bucket: string;
}

interface ParsedArgs {
  [key: string]: string | undefined;
}

interface AuthUserRecord {
  id: string;
  email: string;
}

function parseArgs(argv: string[]): ParsedArgs {
  const parsed: ParsedArgs = {};

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      continue;
    }

    const key = token.slice(2);
    const nextValue = argv[index + 1];
    if (!nextValue || nextValue.startsWith("--")) {
      parsed[key] = "true";
      continue;
    }

    parsed[key] = nextValue;
    index += 1;
  }

  return parsed;
}

function requireArg(args: ParsedArgs, name: string): string {
  const value = (args[name] ?? "").trim();
  if (!value) {
    throw new Error(`Missing required argument --${name}`);
  }

  return value;
}

function buildOptions(argv: string[]): SeedOptions {
  const args = parseArgs(argv);

  return {
    supabaseUrl: requireArg(args, "supabase-url"),
    serviceRoleKey: requireArg(args, "service-role-key"),
    password: requireArg(args, "password"),
    assetRoot: requireArg(args, "asset-root"),
    bucket: (args["bucket"] ?? migrationMediaBucket).trim() || migrationMediaBucket
  };
}

function isTransientSupabaseError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  const normalized = message.toLowerCase();
  return (
    normalized.includes("invalid response") ||
    normalized.includes("fetch failed") ||
    normalized.includes("gateway") ||
    normalized.includes("econnrefused") ||
    normalized.includes("timed out") ||
    normalized.includes("502") ||
    normalized.includes("503")
  );
}

async function delay(milliseconds: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function deriveInitials(displayName: string): string {
  return displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]!.toUpperCase())
    .join("");
}

function buildPlayerCountDisplay(minPlayers: number, maxPlayers: number): string {
  return minPlayers === maxPlayers ? `${minPlayers} player${minPlayers === 1 ? "" : "s"}` : `${minPlayers}-${maxPlayers} players`;
}

function buildAgeDisplay(authority: string, value: string): string {
  return `${authority} ${value}`;
}

function parseMimeType(filePath: string, fallback: string): string {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".svg") {
    return "image/svg+xml";
  }
  if (extension === ".png") {
    return "image/png";
  }
  if (extension === ".jpg" || extension === ".jpeg") {
    return "image/jpeg";
  }
  if (extension === ".webp") {
    return "image/webp";
  }

  return fallback;
}

async function ensureBucket(client: SupabaseClient, bucket: string): Promise<void> {
  const { data, error } = await client.storage.listBuckets();
  if (error) {
    throw error;
  }

  if (data.some((candidate) => candidate.name === bucket)) {
    await client.storage.updateBucket(bucket, {
      public: true,
      fileSizeLimit: "25MB",
      allowedMimeTypes: ["image/png", "image/jpeg", "image/webp", "image/svg+xml"]
    });
    return;
  }

  const { error: createError } = await client.storage.createBucket(bucket, {
    public: true,
    fileSizeLimit: "25MB",
    allowedMimeTypes: ["image/png", "image/jpeg", "image/webp", "image/svg+xml"]
  });
  if (createError) {
    throw createError;
  }
}

async function waitForSupabaseReady(client: SupabaseClient): Promise<void> {
  const timeoutAt = Date.now() + 120_000;
  let lastError = "Supabase HTTP services are still starting.";

  while (Date.now() < timeoutAt) {
    try {
      const [{ error: bucketError }, { error: authError }, { error: restError }] = await Promise.all([
        client.storage.listBuckets(),
        client.auth.admin.listUsers({ page: 1, perPage: 1 }),
        client.from("migration_wave_state").select("key").limit(1)
      ]);

      if (!bucketError && !authError && !restError) {
        return;
      }

      const details = [bucketError?.message, authError?.message, restError?.message].filter(Boolean);
      if (details.length > 0) {
        lastError = details.join(" | ");
      }
    } catch (error: unknown) {
      lastError = error instanceof Error ? error.message : String(error);
    }

    await delay(2000);
  }

  throw new Error(`Timed out waiting for Supabase APIs to become ready. Last error: ${lastError}`);
}

async function uploadAsset(
  client: SupabaseClient,
  bucket: string,
  assetRoot: string,
  relativePath: string,
  storagePath: string,
  fallbackMimeType: string
): Promise<{ storagePath: string; publicUrl: string; mimeType: string }> {
  const fullPath = path.join(assetRoot, relativePath);
  const content = await readFile(fullPath);
  const mimeType = parseMimeType(relativePath, fallbackMimeType);
  const { error } = await client.storage.from(bucket).upload(storagePath, content, {
    contentType: mimeType,
    upsert: true
  });
  if (error) {
    throw error;
  }

  const { data } = client.storage.from(bucket).getPublicUrl(storagePath);
  return {
    storagePath,
    publicUrl: data.publicUrl,
    mimeType
  };
}

async function ensureAuthUsers(client: SupabaseClient, password: string): Promise<Map<string, AuthUserRecord>> {
  const { data, error } = await client.auth.admin.listUsers();
  if (error) {
    throw error;
  }

  const usersByEmail = new Map(
    data.users
      .filter((candidate) => candidate.email)
      .map((candidate) => [candidate.email!.toLowerCase(), { id: candidate.id, email: candidate.email! } satisfies AuthUserRecord])
  );

  const records = new Map<string, AuthUserRecord>();
  for (const fixture of migrationSeedUsers) {
    const existing = usersByEmail.get(fixture.email.toLowerCase());
    if (existing) {
      const { error: updateError } = await client.auth.admin.updateUserById(existing.id, {
        password,
        email_confirm: true,
        user_metadata: {
          userName: fixture.userName,
          displayName: fixture.displayName
        }
      });
      if (updateError) {
        throw updateError;
      }

      records.set(fixture.userName, existing);
      continue;
    }

    const { data: created, error: createError } = await client.auth.admin.createUser({
      email: fixture.email,
      password,
      email_confirm: true,
      user_metadata: {
        userName: fixture.userName,
        displayName: fixture.displayName
      }
    });
    if (createError || !created.user?.id || !created.user.email) {
      throw createError ?? new Error(`Failed to create auth user for ${fixture.userName}`);
    }

    records.set(fixture.userName, { id: created.user.id, email: created.user.email });
  }

  return records;
}

async function resetDemoData(client: SupabaseClient): Promise<void> {
  const { error } = await client.rpc("reset_migration_demo_data");
  if (error) {
    throw error;
  }
}

async function seedOnce(options: SeedOptions): Promise<void> {
  const client = createClient(options.supabaseUrl, options.serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  });

  console.log("==> Waiting for Supabase APIs to become ready");
  await waitForSupabaseReady(client);

  console.log("==> Ensuring Supabase media bucket exists");
  await ensureBucket(client, options.bucket);

  console.log("==> Creating or updating deterministic Supabase auth users");
  const authUsers = await ensureAuthUsers(client, options.password);

  console.log("==> Resetting migration demo tables");
  await resetDemoData(client);

  console.log("==> Seeding application users and role projections");
  const appUserRows = migrationSeedUsers.map((fixture) => {
    const authRecord = authUsers.get(fixture.userName);
    if (!authRecord) {
      throw new Error(`Missing auth user for fixture ${fixture.userName}`);
    }

    return {
      auth_user_id: authRecord.id,
      user_name: fixture.userName,
      display_name: fixture.displayName,
      first_name: fixture.firstName,
      last_name: fixture.lastName,
      email: fixture.email,
      email_verified: true,
      identity_provider: "email",
      avatar_url: `https://api.dicebear.com/9.x/initials/svg?seed=${encodeURIComponent(fixture.displayName)}`,
      avatar_storage_path: null
    };
  });

  const { data: insertedUsers, error: userInsertError } = await client
    .from("app_users")
    .insert(appUserRows)
    .select("id, auth_user_id, user_name");
  if (userInsertError) {
    throw userInsertError;
  }

  const appUsersByUserName = new Map(insertedUsers.map((row) => [row.user_name as string, row.id as string]));
  const appUsersByAuthId = new Map(insertedUsers.map((row) => [row.auth_user_id as string, row.id as string]));

  const roleRows = migrationSeedUsers.flatMap((fixture) => {
    const appUserId = appUsersByUserName.get(fixture.userName);
    if (!appUserId) {
      throw new Error(`Missing app user id for ${fixture.userName}`);
    }

    return fixture.roles.map((role) => ({
      user_id: appUserId,
      role
    }));
  });
  const { error: roleInsertError } = await client.from("app_user_roles").insert(roleRows);
  if (roleInsertError) {
    throw roleInsertError;
  }

  const boardProfileRows = migrationSeedUsers
    .filter((fixture) => fixture.boardUserId)
    .map((fixture) => ({
      user_id: appUsersByUserName.get(fixture.userName),
      board_user_id: fixture.boardUserId,
      display_name: fixture.displayName,
      avatar_url: fixture.boardAvatarUrl ?? null
    }));
  if (boardProfileRows.length > 0) {
    const { error: boardProfileError } = await client.from("user_board_profiles").insert(boardProfileRows);
    if (boardProfileError) {
      throw boardProfileError;
    }
  }

  console.log("==> Uploading studio media and seeding studios");
  const studioRows: Array<Record<string, unknown>> = [];
  for (const studio of migrationSeedStudios) {
    const ownerUserId = appUsersByUserName.get(studio.ownerUserName);
    if (!ownerUserId) {
      throw new Error(`Missing owner user for studio ${studio.slug}`);
    }

    const uploadedLogo = await uploadAsset(
      client,
      options.bucket,
      options.assetRoot,
      studio.logoAssetPath,
      `studios/${studio.slug}/logo${path.extname(studio.logoAssetPath).toLowerCase()}`,
      "image/svg+xml"
    );
    const uploadedBanner = await uploadAsset(
      client,
      options.bucket,
      options.assetRoot,
      studio.bannerAssetPath,
      `studios/${studio.slug}/banner${path.extname(studio.bannerAssetPath).toLowerCase()}`,
      "image/svg+xml"
    );

    studioRows.push({
      slug: studio.slug,
      display_name: studio.displayName,
      description: studio.description,
      logo_url: uploadedLogo.publicUrl,
      logo_storage_path: uploadedLogo.storagePath,
      banner_url: uploadedBanner.publicUrl,
      banner_storage_path: uploadedBanner.storagePath,
      created_by_user_id: ownerUserId
    });
  }

  const { data: insertedStudios, error: studioInsertError } = await client
    .from("studios")
    .insert(studioRows)
    .select("id, slug");
  if (studioInsertError) {
    throw studioInsertError;
  }

  const studiosBySlug = new Map(insertedStudios.map((row) => [row.slug as string, row.id as string]));

  const membershipRows = migrationSeedStudios.map((studio) => ({
    studio_id: studiosBySlug.get(studio.slug),
    user_id: appUsersByUserName.get(studio.ownerUserName),
    role: "owner"
  }));
  const { error: membershipError } = await client.from("studio_memberships").insert(membershipRows);
  if (membershipError) {
    throw membershipError;
  }

  const linkRows = migrationSeedStudios.flatMap((studio) =>
    studio.links.map((link) => ({
      studio_id: studiosBySlug.get(studio.slug),
      label: link.label,
      url: link.url
    }))
  );
  if (linkRows.length > 0) {
    const { error: linkInsertError } = await client.from("studio_links").insert(linkRows);
    if (linkInsertError) {
      throw linkInsertError;
    }
  }

  console.log("==> Uploading title media and seeding public catalog rows");
  const titleRows: Array<Record<string, unknown>> = [];
  const mediaRows: Array<Record<string, unknown>> = [];
  for (const title of migrationSeedTitles) {
    const studioId = studiosBySlug.get(title.studioSlug);
    if (!studioId) {
      throw new Error(`Missing studio ${title.studioSlug} for title ${title.slug}`);
    }

    const titleId = crypto.randomUUID();
    for (const media of title.media) {
      const uploaded = await uploadAsset(
        client,
        options.bucket,
        options.assetRoot,
        media.assetPath,
        `titles/${title.studioSlug}/${title.slug}/${media.role}${path.extname(media.assetPath).toLowerCase()}`,
        media.mimeType
      );
      mediaRows.push({
        title_id: titleId,
        media_role: media.role,
        source_url: uploaded.publicUrl,
        storage_path: uploaded.storagePath,
        alt_text: media.altText,
        mime_type: uploaded.mimeType,
        width: media.width,
        height: media.height
      });
    }

    titleRows.push({
      id: titleId,
      studio_id: studioId,
      slug: title.slug,
      content_kind: title.contentKind,
      lifecycle_status: title.lifecycleStatus,
      visibility: title.visibility,
      is_reported: title.isReported,
      current_metadata_revision: title.currentMetadataRevision,
      display_name: title.displayName,
      short_description: title.shortDescription,
      description: title.description,
      genre_display: title.genreDisplay,
      min_players: title.minPlayers,
      max_players: title.maxPlayers,
      age_rating_authority: title.ageRatingAuthority,
      age_rating_value: title.ageRatingValue,
      min_age_years: title.minAgeYears,
      current_release_id: title.currentReleaseVersion ? crypto.randomUUID() : null,
      current_release_version: title.currentReleaseVersion ?? null,
      current_release_published_at: title.currentReleasePublishedAt ?? null,
      acquisition_url: title.acquisition?.url ?? null,
      acquisition_label: title.acquisition?.label ?? null,
      acquisition_provider_display_name: title.acquisition?.providerDisplayName ?? null,
      acquisition_provider_homepage_url: title.acquisition?.providerHomepageUrl ?? null
    });
  }

  const { error: titleInsertError } = await client.from("titles").insert(titleRows);
  if (titleInsertError) {
    throw titleInsertError;
  }
  const { error: mediaInsertError } = await client.from("title_media_assets").insert(mediaRows);
  if (mediaInsertError) {
    throw mediaInsertError;
  }

  console.log("==> Migration seed complete");
  console.log(`Seeded users use password: ${options.password}`);
  console.log(`Moderator account: alex.rivera (${migrationSeedUsers[0]?.email ?? ""})`);
  console.log(`Developer account: emma.torres (${migrationSeedUsers[1]?.email ?? ""})`);
  console.log(`Media bucket: ${options.bucket}`);
  console.log(`Seeded application users: ${appUsersByAuthId.size}`);
}

async function seed(): Promise<void> {
  const options = buildOptions(process.argv.slice(2));
  const maxAttempts = 10;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      await seedOnce(options);
      return;
    } catch (error: unknown) {
      if (attempt >= maxAttempts || !isTransientSupabaseError(error)) {
        throw error;
      }

      const message = error instanceof Error ? error.message : String(error);
      console.warn(`Transient Supabase startup error during migration seed (attempt ${attempt}/${maxAttempts}): ${message}`);
      await delay(2000);
    }
  }
}

seed().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exitCode = 1;
});
