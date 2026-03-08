import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  localMigrationEnvironment,
  maintainedApiRoutes,
  migrationMediaBucket,
  type CatalogPaging,
  type CatalogTitle,
  type CatalogTitleListResponse,
  type CatalogTitleResponse,
  type CatalogTitleSummary,
  type CurrentUserResponse,
  type DeveloperEnrollmentResponse,
  type DeveloperStudioListResponse,
  type ModerationDeveloperListResponse,
  type PlatformRole,
  type PublicTitleAcquisition,
  type Studio,
  type StudioLink,
  type StudioLinkListResponse,
  type StudioLinkResponse,
  type StudioListResponse,
  type StudioMembershipRole,
  type StudioResponse,
  type TitleLifecycleStatus,
  type TitleMediaAsset,
  type TitleVisibility,
  type UserProfileResponse,
  type VerifiedDeveloperRoleStateResponse
} from "@board-enthusiasts/migration-contract";
import { problem, validationProblem } from "./http";

type AppUserRow = {
  id: string;
  auth_user_id: string;
  user_name: string;
  display_name: string | null;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  email_verified: boolean;
  identity_provider: string | null;
  avatar_url: string | null;
  avatar_storage_path: string | null;
  updated_at: string;
};

type AppUserRoleRow = {
  user_id: string;
  role: PlatformRole;
};

type StudioRow = {
  id: string;
  slug: string;
  display_name: string;
  description: string | null;
  logo_url: string | null;
  logo_storage_path: string | null;
  banner_url: string | null;
  banner_storage_path: string | null;
  created_at: string;
  updated_at: string;
  created_by_user_id: string;
};

type StudioMembershipRow = {
  studio_id: string;
  user_id: string;
  role: StudioMembershipRole;
};

type StudioLinkRow = {
  id: string;
  studio_id: string;
  label: string;
  url: string;
  created_at: string;
  updated_at: string;
};

type TitleRow = {
  id: string;
  studio_id: string;
  slug: string;
  content_kind: "game" | "app";
  lifecycle_status: TitleLifecycleStatus;
  visibility: TitleVisibility;
  is_reported: boolean;
  current_metadata_revision: number;
  display_name: string;
  short_description: string;
  description: string;
  genre_display: string;
  min_players: number;
  max_players: number;
  age_rating_authority: string;
  age_rating_value: string;
  min_age_years: number;
  current_release_id: string | null;
  current_release_version: string | null;
  current_release_published_at: string | null;
  acquisition_url: string | null;
  acquisition_label: string | null;
  acquisition_provider_display_name: string | null;
  acquisition_provider_homepage_url: string | null;
  created_at: string;
  updated_at: string;
};

type TitleMediaAssetRow = {
  id: string;
  title_id: string;
  media_role: "card" | "hero" | "logo";
  source_url: string;
  storage_path: string | null;
  alt_text: string | null;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  created_at: string;
  updated_at: string;
};

type WaveStateRow = {
  key: string;
  value: string;
};

const roleOrder: PlatformRole[] = ["player", "developer", "verified_developer", "moderator", "admin", "super_admin"];
const acceptedImageMimeTypes = new Set(["image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"]);
const maxUploadBytes = 25 * 1024 * 1024;

function sortRoles(roles: PlatformRole[]): PlatformRole[] {
  return [...roles].sort((left, right) => roleOrder.indexOf(left) - roleOrder.indexOf(right));
}

function buildInitials(displayName: string | null, firstName: string | null, lastName: string | null, userName: string | null): string {
  const source = [displayName, [firstName, lastName].filter(Boolean).join(" ").trim(), userName]
    .find((candidate) => candidate && candidate.trim().length > 0)
    ?.trim();

  if (!source) {
    return "BE";
  }

  return source
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

function isAbsoluteUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function validateStudioSlug(slug: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug);
}

function isPublicCatalogTitle(title: TitleRow): boolean {
  return title.visibility === "listed" && (title.lifecycle_status === "testing" || title.lifecycle_status === "published");
}

function isPublicCatalogDetail(title: TitleRow): boolean {
  return title.visibility !== "private" && (title.lifecycle_status === "testing" || title.lifecycle_status === "published");
}

function mapStudioLink(row: StudioLinkRow): StudioLink {
  return {
    id: row.id,
    label: row.label,
    url: row.url,
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}

function mapTitleMediaAsset(row: TitleMediaAssetRow): TitleMediaAsset {
  return {
    id: row.id,
    mediaRole: row.media_role,
    sourceUrl: row.source_url,
    altText: row.alt_text,
    mimeType: row.mime_type,
    width: row.width,
    height: row.height,
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}

function buildAcquisition(row: TitleRow): PublicTitleAcquisition | undefined {
  if (!row.acquisition_url || !row.acquisition_provider_display_name) {
    return undefined;
  }

  return {
    url: row.acquisition_url,
    label: row.acquisition_label,
    providerDisplayName: row.acquisition_provider_display_name,
    providerHomepageUrl: row.acquisition_provider_homepage_url
  };
}

function buildCatalogSummary(title: TitleRow, studio: StudioRow, mediaRows: TitleMediaAssetRow[]): CatalogTitleSummary {
  const cardImageUrl = mediaRows.find((row) => row.media_role === "card")?.source_url ?? null;
  return {
    id: title.id,
    studioId: title.studio_id,
    studioSlug: studio.slug,
    slug: title.slug,
    contentKind: title.content_kind,
    lifecycleStatus: title.lifecycle_status,
    visibility: title.visibility,
    isReported: title.is_reported,
    currentMetadataRevision: title.current_metadata_revision,
    displayName: title.display_name,
    shortDescription: title.short_description,
    genreDisplay: title.genre_display,
    minPlayers: title.min_players,
    maxPlayers: title.max_players,
    playerCountDisplay: buildPlayerCountDisplay(title.min_players, title.max_players),
    ageRatingAuthority: title.age_rating_authority,
    ageRatingValue: title.age_rating_value,
    minAgeYears: title.min_age_years,
    ageDisplay: buildAgeDisplay(title.age_rating_authority, title.age_rating_value),
    cardImageUrl,
    acquisitionUrl: title.acquisition_url
  };
}

function buildCatalogDetail(title: TitleRow, studio: StudioRow, mediaRows: TitleMediaAssetRow[]): CatalogTitle {
  return {
    ...buildCatalogSummary(title, studio, mediaRows),
    description: title.description,
    mediaAssets: mediaRows.map(mapTitleMediaAsset),
    currentRelease:
      title.current_release_id && title.current_release_version && title.current_release_published_at
        ? {
            id: title.current_release_id,
            version: title.current_release_version,
            metadataRevisionNumber: title.current_metadata_revision,
            publishedAt: title.current_release_published_at
          }
        : undefined,
    acquisition: buildAcquisition(title),
    createdAt: title.created_at,
    updatedAt: title.updated_at
  };
}

export interface Env {
  APP_ENV?: string;
  SUPABASE_URL?: string;
  SUPABASE_ANON_KEY?: string;
  SUPABASE_SERVICE_ROLE_KEY?: string;
  SUPABASE_MEDIA_BUCKET?: string;
}

export interface WorkerAppContext {
  envName: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
  supabaseServiceRoleKey: string;
  supabaseMediaBucket: string;
}

export interface MaintainedSurfaceResponse {
  environment: string;
  maintainedApiRoutes: typeof maintainedApiRoutes;
}

interface AuthenticatedUser {
  appUser: AppUserRow;
  roles: PlatformRole[];
}

interface CatalogQuery {
  studioSlug?: string;
  contentKind?: "game" | "app";
  genre?: string;
  sort?: "title" | "genre";
  pageNumber?: number;
  pageSize?: number;
}

interface StudioMutationRequest {
  slug: string;
  displayName: string;
  description?: string | null;
  logoUrl?: string | null;
  bannerUrl?: string | null;
}

interface StudioLinkMutationRequest {
  label: string;
  url: string;
}

function createServiceClient(context: WorkerAppContext): SupabaseClient {
  return createClient(context.supabaseUrl, context.supabaseServiceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  });
}

function parseContext(env: Env): WorkerAppContext {
  const supabaseUrl = (env.SUPABASE_URL ?? "").trim();
  const supabaseAnonKey = (env.SUPABASE_ANON_KEY ?? "").trim();
  const supabaseServiceRoleKey = (env.SUPABASE_SERVICE_ROLE_KEY ?? "").trim();

  if (!supabaseUrl || !supabaseAnonKey || !supabaseServiceRoleKey) {
    throw problem(
      503,
      "migration_environment_incomplete",
      "Migration environment is incomplete.",
      "Supabase URL, anon key, and service role key must be configured for the Workers API."
    );
  }

  return {
    envName: env.APP_ENV?.trim() || "local",
    supabaseUrl,
    supabaseAnonKey,
    supabaseServiceRoleKey,
    supabaseMediaBucket: env.SUPABASE_MEDIA_BUCKET?.trim() || migrationMediaBucket || localMigrationEnvironment.supabaseMediaBucket
  };
}

export function getMaintainedSurface(context: WorkerAppContext): MaintainedSurfaceResponse {
  return {
    environment: context.envName,
    maintainedApiRoutes
  };
}

export class WorkerAppService {
  private readonly context: WorkerAppContext;
  private readonly client: SupabaseClient;

  constructor(env: Env) {
    this.context = parseContext(env);
    this.client = createServiceClient(this.context);
  }

  getContext(): WorkerAppContext {
    return this.context;
  }

  async getReadyState(): Promise<Record<string, unknown>> {
    const { data, error } = await this.client
      .from("migration_wave_state")
      .select("key, value")
      .in("key", ["wave", "status"]);

    if (error) {
      throw problem(503, "migration_supabase_unavailable", "Supabase is not ready.", error.message);
    }

    const waveState = new Map((data as WaveStateRow[]).map((row) => [row.key, row.value]));
    return {
      status: "ready",
      environment: this.context.envName,
      wave: waveState.get("wave") ?? "unknown",
      phaseStatus: waveState.get("status") ?? "unknown",
      supabaseUrlConfigured: true,
      mediaBucket: this.context.supabaseMediaBucket
    };
  }

  async getCurrentUserResponse(token: string): Promise<CurrentUserResponse> {
    const user = await this.requireUser(token);

    return {
      subject: user.appUser.auth_user_id,
      displayName: user.appUser.display_name ?? user.appUser.user_name,
      email: user.appUser.email,
      emailVerified: user.appUser.email_verified,
      identityProvider: user.appUser.identity_provider,
      roles: user.roles
    };
  }

  async getCurrentUserProfile(token: string): Promise<UserProfileResponse> {
    const user = await this.requireUser(token);

    return {
      profile: {
        subject: user.appUser.auth_user_id,
        displayName: user.appUser.display_name,
        userName: user.appUser.user_name,
        firstName: user.appUser.first_name,
        lastName: user.appUser.last_name,
        email: user.appUser.email,
        emailVerified: user.appUser.email_verified,
        avatarUrl: user.appUser.avatar_url,
        avatarDataUrl: null,
        initials: buildInitials(
          user.appUser.display_name,
          user.appUser.first_name,
          user.appUser.last_name,
          user.appUser.user_name
        ),
        updatedAt: user.appUser.updated_at
      }
    };
  }

  async updateCurrentUserProfile(token: string, input: { displayName?: string | null }): Promise<UserProfileResponse> {
    const user = await this.requireUser(token);

    if (input.displayName !== undefined && input.displayName !== null && input.displayName.trim().length === 0) {
      throw validationProblem({
        displayName: ["Display name cannot be empty when supplied."]
      });
    }

    const { error } = await this.client
      .from("app_users")
      .update({
        display_name: input.displayName ?? null,
        updated_at: new Date().toISOString()
      })
      .eq("id", user.appUser.id);

    if (error) {
      throw problem(500, "profile_update_failed", "Profile update failed.", error.message);
    }

    return this.getCurrentUserProfile(token);
  }

  async getDeveloperEnrollment(token: string): Promise<DeveloperEnrollmentResponse> {
    const user = await this.requireUser(token);
    const developerAccessEnabled = user.roles.includes("developer");
    const verifiedDeveloper = user.roles.includes("verified_developer");

    return {
      developerEnrollment: {
        status: developerAccessEnabled ? "enrolled" : "not_enrolled",
        actionRequiredBy: "none",
        developerAccessEnabled,
        verifiedDeveloper,
        canSubmitRequest: !developerAccessEnabled
      }
    };
  }

  async enrollCurrentUserAsDeveloper(token: string): Promise<DeveloperEnrollmentResponse> {
    const user = await this.requireUser(token);
    const alreadyEnrolled = user.roles.includes("developer");
    if (!alreadyEnrolled) {
      const { error } = await this.client.from("app_user_roles").insert({
        user_id: user.appUser.id,
        role: "developer"
      });
      if (error) {
        throw problem(500, "developer_enrollment_failed", "Developer enrollment failed.", error.message);
      }
    }

    return this.getDeveloperEnrollment(token);
  }

  async listModerationDevelopers(token: string, search?: string | null): Promise<ModerationDeveloperListResponse> {
    const user = await this.requireUser(token);
    this.assertModerator(user.roles);

    const developerUserIds = await this.listUserIdsByRole("developer");
    const developers = await this.getUsersByIds(developerUserIds);
    const normalizedSearch = (search ?? "").trim().toLowerCase();

    return {
      developers: developers
        .filter((developer) => {
          if (!normalizedSearch) {
            return true;
          }

          return [developer.user_name, developer.display_name, developer.email]
            .filter((candidate): candidate is string => Boolean(candidate))
            .some((candidate) => candidate.toLowerCase().includes(normalizedSearch));
        })
        .sort((left, right) => (left.display_name ?? left.user_name).localeCompare(right.display_name ?? right.user_name))
        .map((developer) => ({
          developerSubject: developer.auth_user_id,
          userName: developer.user_name,
          displayName: developer.display_name,
          email: developer.email
        }))
    };
  }

  async getVerifiedDeveloperState(token: string, developerIdentifier: string): Promise<VerifiedDeveloperRoleStateResponse> {
    const user = await this.requireUser(token);
    this.assertModerator(user.roles);

    const developer = await this.findDeveloperByIdentifier(developerIdentifier);
    const roles = await this.getRolesForUser(developer.id);
    return {
      verifiedDeveloperRoleState: {
        developerSubject: developer.auth_user_id,
        verifiedDeveloper: roles.includes("verified_developer"),
        alreadyInRequestedState: false
      }
    };
  }

  async setVerifiedDeveloperState(token: string, developerIdentifier: string, verified: boolean): Promise<VerifiedDeveloperRoleStateResponse> {
    const user = await this.requireUser(token);
    this.assertModerator(user.roles);

    const developer = await this.findDeveloperByIdentifier(developerIdentifier);
    const roles = await this.getRolesForUser(developer.id);
    const alreadyInRequestedState = roles.includes("verified_developer") === verified;

    if (!alreadyInRequestedState) {
      if (verified) {
        const { error } = await this.client.from("app_user_roles").insert({
          user_id: developer.id,
          role: "verified_developer"
        });
        if (error) {
          throw problem(500, "verified_developer_role_update_failed", "Verified developer role update failed.", error.message);
        }
      } else {
        const { error } = await this.client
          .from("app_user_roles")
          .delete()
          .eq("user_id", developer.id)
          .eq("role", "verified_developer");
        if (error) {
          throw problem(500, "verified_developer_role_update_failed", "Verified developer role update failed.", error.message);
        }
      }
    }

    return {
      verifiedDeveloperRoleState: {
        developerSubject: developer.auth_user_id,
        verifiedDeveloper: verified,
        alreadyInRequestedState
      }
    };
  }

  async listPublicStudios(): Promise<StudioListResponse> {
    const studios = await this.getStudios();
    const linksByStudioId = await this.getStudioLinksByStudioIds(studios.map((studio) => studio.id));

    return {
      studios: studios
        .sort((left, right) => left.display_name.localeCompare(right.display_name))
        .map((studio) => this.buildStudioSummary(studio, linksByStudioId.get(studio.id) ?? []))
    };
  }

  async getPublicStudio(slug: string): Promise<StudioResponse> {
    const studio = await this.getStudioBySlug(slug);
    const linksByStudioId = await this.getStudioLinksByStudioIds([studio.id]);

    return {
      studio: this.buildStudio(studio, linksByStudioId.get(studio.id) ?? [])
    };
  }

  async listManagedStudios(token: string): Promise<DeveloperStudioListResponse> {
    const user = await this.requireUser(token);
    const memberships = await this.getStudioMembershipsForUser(user.appUser.id);
    const studios = memberships.length > 0 ? await this.getStudiosByIds(memberships.map((membership) => membership.studio_id)) : [];
    const linksByStudioId = await this.getStudioLinksByStudioIds(studios.map((studio) => studio.id));
    const roleByStudioId = new Map(memberships.map((membership) => [membership.studio_id, membership.role]));

    return {
      studios: studios
        .sort((left, right) => left.display_name.localeCompare(right.display_name))
        .map((studio) => ({
          ...this.buildStudioSummary(studio, linksByStudioId.get(studio.id) ?? []),
          role: roleByStudioId.get(studio.id) ?? "editor"
        }))
    };
  }

  async createStudio(token: string, input: StudioMutationRequest): Promise<StudioResponse> {
    const user = await this.requireUser(token);
    if (!this.canCreateStudio(user.roles)) {
      throw problem(403, "developer_access_required", "Developer access is required.", "Only developers and above can create studios.");
    }

    this.validateStudioMutation(input);
    const existing = await this.findStudioBySlug(input.slug);
    if (existing) {
      throw problem(409, "studio_slug_conflict", "Studio already exists", "The supplied studio slug is already in use.");
    }

    const now = new Date().toISOString();
    const { data, error } = await this.client
      .from("studios")
      .insert({
        slug: input.slug,
        display_name: input.displayName,
        description: input.description ?? null,
        logo_url: input.logoUrl ?? null,
        banner_url: input.bannerUrl ?? null,
        created_by_user_id: user.appUser.id,
        created_at: now,
        updated_at: now
      })
      .select("*")
      .single();
    if (error) {
      throw problem(500, "studio_create_failed", "Studio creation failed.", error.message);
    }

    const studio = data as unknown as StudioRow;
    const { error: membershipError } = await this.client.from("studio_memberships").insert({
      studio_id: studio.id,
      user_id: user.appUser.id,
      role: "owner",
      joined_at: now,
      updated_at: now
    });
    if (membershipError) {
      throw problem(500, "studio_create_failed", "Studio creation failed.", membershipError.message);
    }

    return {
      studio: this.buildStudio(studio, [])
    };
  }

  async updateStudio(token: string, studioId: string, input: StudioMutationRequest): Promise<StudioResponse> {
    const user = await this.requireUser(token);
    const studio = await this.getStudioById(studioId);
    await this.requireStudioAccess(user.appUser.id, studio.id);
    this.validateStudioMutation(input);

    const existing = await this.findStudioBySlug(input.slug);
    if (existing && existing.id !== studio.id) {
      throw problem(409, "studio_slug_conflict", "Studio already exists", "The supplied studio slug is already in use.");
    }

    const { error } = await this.client
      .from("studios")
      .update({
        slug: input.slug,
        display_name: input.displayName,
        description: input.description ?? null,
        logo_url: input.logoUrl ?? null,
        banner_url: input.bannerUrl ?? null,
        updated_at: new Date().toISOString()
      })
      .eq("id", studio.id);
    if (error) {
      throw problem(500, "studio_update_failed", "Studio update failed.", error.message);
    }

    const refreshedStudio = await this.getStudioById(studio.id);
    const links = (await this.getStudioLinksByStudioIds([studio.id])).get(studio.id) ?? [];
    return {
      studio: this.buildStudio(refreshedStudio, links)
    };
  }

  async deleteStudio(token: string, studioId: string): Promise<void> {
    const user = await this.requireUser(token);
    await this.requireStudioOwner(user.appUser.id, studioId);

    const { error } = await this.client.from("studios").delete().eq("id", studioId);
    if (error) {
      throw problem(500, "studio_delete_failed", "Studio delete failed.", error.message);
    }
  }

  async listStudioLinks(token: string, studioId: string): Promise<StudioLinkListResponse> {
    const user = await this.requireUser(token);
    await this.requireStudioAccess(user.appUser.id, studioId);

    return {
      links: (await this.getStudioLinksByStudioIds([studioId])).get(studioId)?.map(mapStudioLink) ?? []
    };
  }

  async createStudioLink(token: string, studioId: string, input: StudioLinkMutationRequest): Promise<StudioLinkResponse> {
    const user = await this.requireUser(token);
    await this.requireStudioAccess(user.appUser.id, studioId);
    this.validateStudioLinkMutation(input);

    const { data, error } = await this.client
      .from("studio_links")
      .insert({
        studio_id: studioId,
        label: input.label,
        url: input.url,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select("*")
      .single();
    if (error) {
      throw problem(500, "studio_link_create_failed", "Studio link create failed.", error.message);
    }

    return {
      link: mapStudioLink(data as unknown as StudioLinkRow)
    };
  }

  async updateStudioLink(token: string, studioId: string, linkId: string, input: StudioLinkMutationRequest): Promise<StudioLinkResponse> {
    const user = await this.requireUser(token);
    await this.requireStudioAccess(user.appUser.id, studioId);
    this.validateStudioLinkMutation(input);
    await this.requireStudioLink(studioId, linkId);

    const { data, error } = await this.client
      .from("studio_links")
      .update({
        label: input.label,
        url: input.url,
        updated_at: new Date().toISOString()
      })
      .eq("id", linkId)
      .eq("studio_id", studioId)
      .select("*")
      .single();
    if (error) {
      throw problem(500, "studio_link_update_failed", "Studio link update failed.", error.message);
    }

    return {
      link: mapStudioLink(data as unknown as StudioLinkRow)
    };
  }

  async deleteStudioLink(token: string, studioId: string, linkId: string): Promise<void> {
    const user = await this.requireUser(token);
    await this.requireStudioAccess(user.appUser.id, studioId);
    await this.requireStudioLink(studioId, linkId);

    const { error } = await this.client.from("studio_links").delete().eq("id", linkId).eq("studio_id", studioId);
    if (error) {
      throw problem(500, "studio_link_delete_failed", "Studio link delete failed.", error.message);
    }
  }

  async uploadStudioMedia(token: string, studioId: string, kind: "logo" | "banner", file: File | null): Promise<StudioResponse> {
    const user = await this.requireUser(token);
    const studio = await this.getStudioById(studioId);
    await this.requireStudioAccess(user.appUser.id, studio.id);
    const validatedFile = this.requireUploadFile(file);

    const extension = this.extensionForMimeType(validatedFile.type);
    const storagePath = `studios/${studio.slug}/${kind}${extension}`;
    const { error: uploadError } = await this.client.storage
      .from(this.context.supabaseMediaBucket)
      .upload(storagePath, validatedFile, { contentType: validatedFile.type, upsert: true });
    if (uploadError) {
      throw problem(500, "studio_media_upload_failed", "Studio media upload failed.", uploadError.message);
    }

    const publicUrl = this.client.storage.from(this.context.supabaseMediaBucket).getPublicUrl(storagePath).data.publicUrl;
    const updatePayload =
      kind === "logo"
        ? {
            logo_url: publicUrl,
            logo_storage_path: storagePath,
            updated_at: new Date().toISOString()
          }
        : {
            banner_url: publicUrl,
            banner_storage_path: storagePath,
            updated_at: new Date().toISOString()
          };
    const { error: updateError } = await this.client.from("studios").update(updatePayload).eq("id", studio.id);
    if (updateError) {
      throw problem(500, "studio_media_upload_failed", "Studio media upload failed.", updateError.message);
    }

    const links = (await this.getStudioLinksByStudioIds([studio.id])).get(studio.id) ?? [];
    const refreshedStudio = await this.getStudioById(studio.id);
    return {
      studio: this.buildStudio(refreshedStudio, links)
    };
  }

  async listCatalogTitles(query: CatalogQuery): Promise<CatalogTitleListResponse> {
    const allTitles = await this.getTitles();
    const allStudios = await this.getStudiosByIds(allTitles.map((title) => title.studio_id));
    const studiosById = new Map(allStudios.map((studio) => [studio.id, studio]));
    const mediaByTitleId = await this.getTitleMediaByTitleIds(allTitles.map((title) => title.id));

    const validatedSort = query.sort ?? "title";
    if (!["title", "genre"].includes(validatedSort)) {
      throw validationProblem({
        sort: ["Sort must be one of: title, genre."]
      });
    }

    const pageNumber = query.pageNumber ?? 1;
    const pageSize = query.pageSize ?? 12;
    const validationErrors: Record<string, string[]> = {};
    if (pageNumber < 1) {
      validationErrors.pageNumber = ["Page number must be at least 1."];
    }
    if (pageSize < 1 || pageSize > 48) {
      validationErrors.pageSize = ["Page size must be between 1 and 48."];
    }
    if (Object.keys(validationErrors).length > 0) {
      throw validationProblem(validationErrors);
    }

    const matchingTitles = allTitles
      .filter(isPublicCatalogTitle)
      .filter((title) => !query.contentKind || title.content_kind === query.contentKind)
      .filter((title) => !query.genre || title.genre_display === query.genre)
      .filter((title) => {
        if (!query.studioSlug) {
          return true;
        }

        return studiosById.get(title.studio_id)?.slug === query.studioSlug;
      })
      .sort((left, right) => {
        if (validatedSort === "genre") {
          return left.genre_display.localeCompare(right.genre_display) || left.display_name.localeCompare(right.display_name);
        }

        return left.display_name.localeCompare(right.display_name);
      });

    const totalCount = matchingTitles.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
    const sliceStart = (pageNumber - 1) * pageSize;
    const pagedTitles = matchingTitles.slice(sliceStart, sliceStart + pageSize);

    return {
      titles: pagedTitles.map((title) => {
        const studio = studiosById.get(title.studio_id);
        if (!studio) {
          throw problem(500, "catalog_join_failed", "Catalog projection failed.", `Studio ${title.studio_id} was not found.`);
        }

        return buildCatalogSummary(title, studio, mediaByTitleId.get(title.id) ?? []);
      }),
      paging: {
        pageNumber,
        pageSize,
        totalCount,
        totalPages,
        hasPreviousPage: pageNumber > 1,
        hasNextPage: pageNumber < totalPages
      } satisfies CatalogPaging
    };
  }

  async getCatalogTitle(studioSlug: string, titleSlug: string): Promise<CatalogTitleResponse> {
    const studio = await this.getStudioBySlug(studioSlug);
    const title = await this.getTitleByStudioAndSlug(studio.id, titleSlug);
    if (!isPublicCatalogDetail(title)) {
      throw problem(404, "catalog_title_not_found", "Catalog title not found", "The requested title was not found.");
    }

    const mediaByTitleId = await this.getTitleMediaByTitleIds([title.id]);
    return {
      title: buildCatalogDetail(title, studio, mediaByTitleId.get(title.id) ?? [])
    };
  }

  private async requireUser(token: string): Promise<AuthenticatedUser> {
    const bearerToken = token.trim();
    if (!bearerToken) {
      throw problem(401, "unauthorized", "Unauthorized", "A bearer token is required.");
    }

    const { data, error } = await this.client.auth.getUser(bearerToken);
    if (error || !data.user?.id) {
      throw problem(401, "unauthorized", "Unauthorized", "The supplied bearer token is invalid or expired.");
    }

    const { data: appUserRows, error: appUserError } = await this.client
      .from("app_users")
      .select("*")
      .eq("auth_user_id", data.user.id)
      .limit(1);
    if (appUserError) {
      throw problem(500, "identity_projection_failed", "Identity lookup failed.", appUserError.message);
    }

    const appUser = (appUserRows as AppUserRow[])[0];
    if (!appUser) {
      throw problem(404, "current_user_not_projected", "Current user was not found.", "No application user projection exists for the current bearer token.");
    }

    const roles = await this.getRolesForUser(appUser.id);
    return { appUser, roles };
  }

  private async listUserIdsByRole(role: PlatformRole): Promise<string[]> {
    const { data, error } = await this.client.from("app_user_roles").select("user_id").eq("role", role);
    if (error) {
      throw problem(500, "role_lookup_failed", "Role lookup failed.", error.message);
    }

    return (data as AppUserRoleRow[]).map((row) => row.user_id);
  }

  private async getRolesForUser(userId: string): Promise<PlatformRole[]> {
    const { data, error } = await this.client.from("app_user_roles").select("user_id, role").eq("user_id", userId);
    if (error) {
      throw problem(500, "role_lookup_failed", "Role lookup failed.", error.message);
    }

    return sortRoles((data as AppUserRoleRow[]).map((row) => row.role));
  }

  private async getUsersByIds(userIds: string[]): Promise<AppUserRow[]> {
    if (userIds.length === 0) {
      return [];
    }

    const { data, error } = await this.client.from("app_users").select("*").in("id", userIds);
    if (error) {
      throw problem(500, "user_lookup_failed", "User lookup failed.", error.message);
    }

    return data as AppUserRow[];
  }

  private assertModerator(roles: PlatformRole[]): void {
    if (!roles.some((role) => role === "moderator" || role === "admin" || role === "super_admin")) {
      throw problem(
        403,
        "moderator_access_required",
        "Moderator access is required.",
        "Only moderators and above can view developer moderation tools."
      );
    }
  }

  private canCreateStudio(roles: PlatformRole[]): boolean {
    return roles.some((role) => role === "developer" || role === "verified_developer" || role === "admin" || role === "super_admin");
  }

  private validateStudioMutation(input: StudioMutationRequest): void {
    const errors: Record<string, string[]> = {};

    if (!validateStudioSlug(input.slug)) {
      errors.slug = ["Slug must contain only lowercase letters, numbers, and single hyphen separators."];
    }
    if (!input.displayName || input.displayName.trim().length === 0) {
      errors.displayName = ["Display name is required."];
    }
    if (input.logoUrl && !isAbsoluteUrl(input.logoUrl)) {
      errors.logoUrl = ["Logo URL must be an absolute URI."];
    }
    if (input.bannerUrl && !isAbsoluteUrl(input.bannerUrl)) {
      errors.bannerUrl = ["Banner URL must be an absolute URI."];
    }

    if (Object.keys(errors).length > 0) {
      throw validationProblem(errors);
    }
  }

  private validateStudioLinkMutation(input: StudioLinkMutationRequest): void {
    const errors: Record<string, string[]> = {};
    if (!input.label || input.label.trim().length === 0) {
      errors.label = ["Label is required."];
    }
    if (!input.url || !isAbsoluteUrl(input.url)) {
      errors.url = ["URL must be an absolute URI."];
    }

    if (Object.keys(errors).length > 0) {
      throw validationProblem(errors);
    }
  }

  private requireUploadFile(file: File | null): File {
    if (!file) {
      throw validationProblem({
        media: ["A media file is required."]
      });
    }
    if (!acceptedImageMimeTypes.has(file.type)) {
      throw validationProblem({
        media: ["Media image format must be JPEG, PNG, WEBP, GIF, or SVG."]
      });
    }
    if (file.size > maxUploadBytes) {
      throw validationProblem({
        media: ["Media image size must be 25 MB or less."]
      });
    }

    return file;
  }

  private extensionForMimeType(mimeType: string): string {
    switch (mimeType) {
      case "image/png":
        return ".png";
      case "image/jpeg":
        return ".jpg";
      case "image/webp":
        return ".webp";
      case "image/gif":
        return ".gif";
      case "image/svg+xml":
        return ".svg";
      default:
        return "";
    }
  }

  private async findDeveloperByIdentifier(identifier: string): Promise<AppUserRow> {
    const { data, error } = await this.client.from("app_users").select("*").or(`user_name.eq.${identifier},auth_user_id.eq.${identifier}`);
    if (error) {
      throw problem(500, "developer_lookup_failed", "Developer lookup failed.", error.message);
    }

    const developer = (data as AppUserRow[])[0];
    if (!developer) {
      throw problem(404, "developer_not_found", "Developer was not found.", "The target developer was not found.");
    }

    const roles = await this.getRolesForUser(developer.id);
    if (!roles.includes("developer")) {
      throw problem(404, "developer_not_found", "Developer was not found.", "The target developer was not found.");
    }

    return developer;
  }

  private async getStudios(): Promise<StudioRow[]> {
    const { data, error } = await this.client.from("studios").select("*");
    if (error) {
      throw problem(500, "studio_lookup_failed", "Studio lookup failed.", error.message);
    }

    return data as StudioRow[];
  }

  private async getStudiosByIds(studioIds: string[]): Promise<StudioRow[]> {
    if (studioIds.length === 0) {
      return [];
    }

    const { data, error } = await this.client.from("studios").select("*").in("id", studioIds);
    if (error) {
      throw problem(500, "studio_lookup_failed", "Studio lookup failed.", error.message);
    }

    return data as StudioRow[];
  }

  private async getStudioBySlug(slug: string): Promise<StudioRow> {
    const studio = await this.findStudioBySlug(slug);
    if (!studio) {
      throw problem(404, "studio_not_found", "Studio not found", "The requested studio was not found.");
    }

    return studio;
  }

  private async getStudioById(studioId: string): Promise<StudioRow> {
    const { data, error } = await this.client.from("studios").select("*").eq("id", studioId).limit(1);
    if (error) {
      throw problem(500, "studio_lookup_failed", "Studio lookup failed.", error.message);
    }

    const studio = (data as StudioRow[])[0];
    if (!studio) {
      throw problem(404, "studio_not_found", "Studio not found", "The requested studio was not found.");
    }

    return studio;
  }

  private async findStudioBySlug(slug: string): Promise<StudioRow | null> {
    const { data, error } = await this.client.from("studios").select("*").eq("slug", slug).limit(1);
    if (error) {
      throw problem(500, "studio_lookup_failed", "Studio lookup failed.", error.message);
    }

    return (data as StudioRow[])[0] ?? null;
  }

  private async getStudioMembershipsForUser(userId: string): Promise<StudioMembershipRow[]> {
    const { data, error } = await this.client.from("studio_memberships").select("*").eq("user_id", userId);
    if (error) {
      throw problem(500, "studio_membership_lookup_failed", "Studio membership lookup failed.", error.message);
    }

    return data as StudioMembershipRow[];
  }

  private async requireStudioAccess(userId: string, studioId: string): Promise<StudioMembershipRow> {
    const { data, error } = await this.client
      .from("studio_memberships")
      .select("*")
      .eq("studio_id", studioId)
      .eq("user_id", userId)
      .limit(1);
    if (error) {
      throw problem(500, "studio_membership_lookup_failed", "Studio membership lookup failed.", error.message);
    }

    const membership = (data as StudioMembershipRow[])[0];
    if (!membership) {
      throw problem(403, "studio_access_required", "Studio access is required.", "Caller does not have permission to manage this studio.");
    }

    return membership;
  }

  private async requireStudioOwner(userId: string, studioId: string): Promise<void> {
    const membership = await this.requireStudioAccess(userId, studioId);
    if (membership.role !== "owner") {
      throw problem(403, "studio_owner_required", "Studio owner access is required.", "Caller does not have permission to delete this studio.");
    }
  }

  private async getStudioLinksByStudioIds(studioIds: string[]): Promise<Map<string, StudioLinkRow[]>> {
    const linksByStudioId = new Map<string, StudioLinkRow[]>();
    if (studioIds.length === 0) {
      return linksByStudioId;
    }

    const { data, error } = await this.client.from("studio_links").select("*").in("studio_id", studioIds);
    if (error) {
      throw problem(500, "studio_link_lookup_failed", "Studio link lookup failed.", error.message);
    }

    for (const row of data as StudioLinkRow[]) {
      const current = linksByStudioId.get(row.studio_id) ?? [];
      current.push(row);
      linksByStudioId.set(row.studio_id, current);
    }

    for (const links of linksByStudioId.values()) {
      links.sort((left, right) => left.label.localeCompare(right.label));
    }

    return linksByStudioId;
  }

  private buildStudioSummary(studio: StudioRow, links: StudioLinkRow[]): Studio {
    return {
      id: studio.id,
      slug: studio.slug,
      displayName: studio.display_name,
      description: studio.description,
      logoUrl: studio.logo_url,
      bannerUrl: studio.banner_url,
      links: links.map(mapStudioLink),
      createdAt: studio.created_at,
      updatedAt: studio.updated_at
    };
  }

  private buildStudio(studio: StudioRow, links: StudioLinkRow[]): Studio {
    return this.buildStudioSummary(studio, links);
  }

  private async requireStudioLink(studioId: string, linkId: string): Promise<void> {
    const { data, error } = await this.client.from("studio_links").select("id").eq("id", linkId).eq("studio_id", studioId).limit(1);
    if (error) {
      throw problem(500, "studio_link_lookup_failed", "Studio link lookup failed.", error.message);
    }

    if ((data as Array<{ id: string }>).length === 0) {
      throw problem(404, "studio_link_not_found", "Studio or link not found.", "Studio or link not found.");
    }
  }

  private async getTitles(): Promise<TitleRow[]> {
    const { data, error } = await this.client.from("titles").select("*");
    if (error) {
      throw problem(500, "catalog_lookup_failed", "Catalog lookup failed.", error.message);
    }

    return data as TitleRow[];
  }

  private async getTitleByStudioAndSlug(studioId: string, titleSlug: string): Promise<TitleRow> {
    const { data, error } = await this.client
      .from("titles")
      .select("*")
      .eq("studio_id", studioId)
      .eq("slug", titleSlug)
      .limit(1);
    if (error) {
      throw problem(500, "catalog_lookup_failed", "Catalog lookup failed.", error.message);
    }

    const title = (data as TitleRow[])[0];
    if (!title) {
      throw problem(404, "catalog_title_not_found", "Catalog title not found", "The requested title was not found.");
    }

    return title;
  }

  private async getTitleMediaByTitleIds(titleIds: string[]): Promise<Map<string, TitleMediaAssetRow[]>> {
    const mediaByTitleId = new Map<string, TitleMediaAssetRow[]>();
    if (titleIds.length === 0) {
      return mediaByTitleId;
    }

    const { data, error } = await this.client.from("title_media_assets").select("*").in("title_id", titleIds);
    if (error) {
      throw problem(500, "catalog_media_lookup_failed", "Catalog media lookup failed.", error.message);
    }

    for (const row of data as TitleMediaAssetRow[]) {
      const current = mediaByTitleId.get(row.title_id) ?? [];
      current.push(row);
      mediaByTitleId.set(row.title_id, current);
    }

    for (const rows of mediaByTitleId.values()) {
      rows.sort((left, right) => left.media_role.localeCompare(right.media_role));
    }

    return mediaByTitleId;
  }
}
