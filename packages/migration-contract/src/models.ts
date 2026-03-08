export interface MigrationEnvironmentLayout {
  appName: string;
  frontendBaseUrl: string;
  apiBaseUrl: string;
  supabaseProjectRef: string;
  supabaseUrl: string;
  supabaseAnonKeyVariable: string;
  supabaseServiceRoleKeyVariable: string;
  supabaseMediaBucket: string;
}

export type PlatformRole =
  | "player"
  | "developer"
  | "verified_developer"
  | "moderator"
  | "admin"
  | "super_admin";

export type StudioMembershipRole = "owner" | "admin" | "editor";
export type TitleContentKind = "game" | "app";
export type TitleLifecycleStatus = "draft" | "testing" | "published" | "archived";
export type TitleVisibility = "private" | "unlisted" | "listed";
export type TitleMediaRole = "card" | "hero" | "logo";

export interface CurrentUserResponse {
  subject: string;
  displayName: string;
  email: string | null;
  emailVerified: boolean;
  identityProvider: string | null;
  roles: PlatformRole[];
}

export interface UserProfile {
  subject: string;
  displayName: string | null;
  userName: string | null;
  firstName: string | null;
  lastName: string | null;
  email: string | null;
  emailVerified: boolean;
  avatarUrl: string | null;
  avatarDataUrl: string | null;
  initials: string;
  updatedAt: string;
}

export interface UserProfileResponse {
  profile: UserProfile;
}

export interface DeveloperEnrollment {
  status: "not_enrolled" | "enrolled";
  actionRequiredBy: "none";
  developerAccessEnabled: boolean;
  verifiedDeveloper: boolean;
  canSubmitRequest: boolean;
}

export interface DeveloperEnrollmentResponse {
  developerEnrollment: DeveloperEnrollment;
}

export interface ModerationDeveloperSummary {
  developerSubject: string;
  userName: string | null;
  displayName: string | null;
  email: string | null;
}

export interface ModerationDeveloperListResponse {
  developers: ModerationDeveloperSummary[];
}

export interface VerifiedDeveloperRoleState {
  developerSubject: string;
  verifiedDeveloper: boolean;
  alreadyInRequestedState: boolean;
}

export interface VerifiedDeveloperRoleStateResponse {
  verifiedDeveloperRoleState: VerifiedDeveloperRoleState;
}

export interface StudioLink {
  id: string;
  label: string;
  url: string;
  createdAt: string;
  updatedAt: string;
}

export interface StudioSummary {
  id: string;
  slug: string;
  displayName: string;
  description: string | null;
  logoUrl: string | null;
  bannerUrl: string | null;
  links: StudioLink[];
}

export interface Studio extends StudioSummary {
  createdAt: string;
  updatedAt: string;
}

export interface StudioResponse {
  studio: Studio;
}

export interface StudioListResponse {
  studios: StudioSummary[];
}

export interface DeveloperStudioSummary extends StudioSummary {
  role: StudioMembershipRole;
}

export interface DeveloperStudioListResponse {
  studios: DeveloperStudioSummary[];
}

export interface StudioLinkListResponse {
  links: StudioLink[];
}

export interface StudioLinkResponse {
  link: StudioLink;
}

export interface TitleMediaAsset {
  id: string;
  mediaRole: TitleMediaRole;
  sourceUrl: string;
  altText: string | null;
  mimeType: string | null;
  width: number | null;
  height: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface CurrentTitleRelease {
  id: string;
  version: string;
  metadataRevisionNumber: number;
  publishedAt: string;
}

export interface PublicTitleAcquisition {
  url: string;
  label: string | null;
  providerDisplayName: string;
  providerHomepageUrl: string | null;
}

export interface CatalogTitleSummary {
  id: string;
  studioId: string;
  studioSlug: string;
  slug: string;
  contentKind: TitleContentKind;
  lifecycleStatus: TitleLifecycleStatus;
  visibility: TitleVisibility;
  isReported: boolean;
  currentMetadataRevision: number;
  displayName: string;
  shortDescription: string;
  genreDisplay: string;
  minPlayers: number;
  maxPlayers: number;
  playerCountDisplay: string;
  ageRatingAuthority: string;
  ageRatingValue: string;
  minAgeYears: number;
  ageDisplay: string;
  cardImageUrl: string | null;
  acquisitionUrl: string | null;
}

export interface CatalogPaging {
  pageNumber: number;
  pageSize: number;
  totalCount: number;
  totalPages: number;
  hasPreviousPage: boolean;
  hasNextPage: boolean;
}

export interface CatalogTitleListResponse {
  titles: CatalogTitleSummary[];
  paging: CatalogPaging;
}

export interface CatalogTitle extends CatalogTitleSummary {
  description: string;
  mediaAssets: TitleMediaAsset[];
  currentRelease?: CurrentTitleRelease;
  acquisition?: PublicTitleAcquisition;
  createdAt: string;
  updatedAt: string;
}

export interface CatalogTitleResponse {
  title: CatalogTitle;
}

export interface ProblemDetails {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  code?: string;
}

export interface ValidationProblemDetails extends ProblemDetails {
  errors: Record<string, string[]>;
}

export interface MigrationSeedUserFixture {
  userName: string;
  email: string;
  displayName: string;
  firstName: string;
  lastName: string;
  roles: PlatformRole[];
  boardUserId?: string;
  boardAvatarUrl?: string;
}

export interface MigrationSeedStudioFixture {
  slug: string;
  displayName: string;
  description: string;
  ownerUserName: string;
  links: Array<{ label: string; url: string }>;
  logoAssetPath: string;
  bannerAssetPath: string;
}

export interface MigrationSeedTitleFixture {
  studioSlug: string;
  slug: string;
  displayName: string;
  contentKind: TitleContentKind;
  lifecycleStatus: TitleLifecycleStatus;
  visibility: TitleVisibility;
  isReported: boolean;
  currentMetadataRevision: number;
  shortDescription: string;
  description: string;
  genreDisplay: string;
  minPlayers: number;
  maxPlayers: number;
  ageRatingAuthority: string;
  ageRatingValue: string;
  minAgeYears: number;
  currentReleaseVersion?: string;
  currentReleasePublishedAt?: string;
  acquisition?: {
    url: string;
    label: string | null;
    providerDisplayName: string;
    providerHomepageUrl: string | null;
  };
  media: Array<{
    role: TitleMediaRole;
    assetPath: string;
    altText: string;
    mimeType: string;
    width: number | null;
    height: number | null;
  }>;
}

export const migrationMediaBucket = "catalog-media";

export const migrationSeedUsers: ReadonlyArray<MigrationSeedUserFixture> = [
  {
    userName: "alex.rivera",
    email: "alex.rivera@boardtpl.local",
    displayName: "Alex Rivera",
    firstName: "Alex",
    lastName: "Rivera",
    roles: ["player", "moderator", "admin", "super_admin"],
    boardUserId: "board_alex_rivera",
    boardAvatarUrl: "https://cdn.board.fun/avatars/board_alex_rivera.png"
  },
  {
    userName: "emma.torres",
    email: "emma.torres@boardtpl.local",
    displayName: "Emma Torres",
    firstName: "Emma",
    lastName: "Torres",
    roles: ["player", "developer", "verified_developer"],
    boardUserId: "board_emma_torres",
    boardAvatarUrl: "https://cdn.board.fun/avatars/board_emma_torres.png"
  },
  {
    userName: "olivia.bennett",
    email: "olivia.bennett@boardtpl.local",
    displayName: "Olivia Bennett",
    firstName: "Olivia",
    lastName: "Bennett",
    roles: ["player", "developer"]
  },
  {
    userName: "ava.garcia",
    email: "ava.garcia@boardtpl.local",
    displayName: "Ava Garcia",
    firstName: "Ava",
    lastName: "Garcia",
    roles: ["player"]
  }
];

export const migrationSeedStudios: ReadonlyArray<MigrationSeedStudioFixture> = [
  {
    slug: "blue-harbor-games",
    displayName: "Blue Harbor Games",
    description: "Co-op adventures with bright maritime themes and approachable controls.",
    ownerUserName: "emma.torres",
    links: [
      { label: "Discord", url: "https://discord.gg/blueharborgames" },
      { label: "YouTube", url: "https://www.youtube.com/@BlueHarborGames" }
    ],
    logoAssetPath: "studios/blue-harbor-games/logo.svg",
    bannerAssetPath: "studios/blue-harbor-games/banner.svg"
  },
  {
    slug: "tiny-orbit-forge",
    displayName: "Tiny Orbit Forge",
    description: "Sci-fi builders featuring modular crafting and community challenges.",
    ownerUserName: "olivia.bennett",
    links: [
      { label: "Discord", url: "https://discord.gg/tinyorbitforge" },
      { label: "YouTube", url: "https://www.youtube.com/@TinyOrbitForge" }
    ],
    logoAssetPath: "studios/tiny-orbit-forge/logo.svg",
    bannerAssetPath: "studios/tiny-orbit-forge/banner.svg"
  }
];

export const migrationSeedTitles: ReadonlyArray<MigrationSeedTitleFixture> = [
  {
    studioSlug: "blue-harbor-games",
    slug: "lantern-drift",
    displayName: "Lantern Drift",
    contentKind: "game",
    lifecycleStatus: "published",
    visibility: "listed",
    isReported: false,
    currentMetadataRevision: 2,
    shortDescription: "Guide glowing paper boats through a midnight canal festival without snuffing the flame.",
    description:
      "Tilt waterways, spin lock-gates, and weave through fireworks as every lantern casts new puzzle shadows across the river. Developed by Blue Harbor Games.",
    genreDisplay: "Puzzle, Family",
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.0",
    currentReleasePublishedAt: "2026-03-07T12:00:00Z",
    acquisition: {
      url: "https://blue-harbor-games.example/titles/lantern-drift",
      label: "Open publisher page",
      providerDisplayName: "Blue Harbor Games Direct",
      providerHomepageUrl: "https://blue-harbor-games.example"
    },
    media: [
      { role: "card", assetPath: "lantern-drift/card.png", altText: "Lantern Drift card art", mimeType: "image/png", width: 900, height: 1280 },
      { role: "hero", assetPath: "lantern-drift/hero.png", altText: "Lantern Drift hero art", mimeType: "image/png", width: 1600, height: 900 },
      { role: "logo", assetPath: "lantern-drift/logo.png", altText: "Lantern Drift logo", mimeType: "image/png", width: 1200, height: 400 }
    ]
  },
  {
    studioSlug: "blue-harbor-games",
    slug: "compass-echo",
    displayName: "Compass Echo",
    contentKind: "app",
    lifecycleStatus: "testing",
    visibility: "listed",
    isReported: false,
    currentMetadataRevision: 1,
    shortDescription: "Plot expedition routes, track secrets, and sync clue boards for sprawling adventures.",
    description:
      "Compass Echo is a premium companion app for campaign nights, with layered maps, route planning, and clue pinning for cooperative exploration games.",
    genreDisplay: "Companion, Utility, Exploration",
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "0.9.0",
    currentReleasePublishedAt: "2026-03-06T18:30:00Z",
    acquisition: {
      url: "https://blue-harbor-games.example/titles/compass-echo",
      label: "Open publisher page",
      providerDisplayName: "Blue Harbor Games Direct",
      providerHomepageUrl: "https://blue-harbor-games.example"
    },
    media: [
      { role: "card", assetPath: "compass-echo/card.png", altText: "Compass Echo card art", mimeType: "image/png", width: 900, height: 1280 },
      { role: "hero", assetPath: "compass-echo/hero.png", altText: "Compass Echo hero art", mimeType: "image/png", width: 1600, height: 900 },
      { role: "logo", assetPath: "compass-echo/logo.png", altText: "Compass Echo logo", mimeType: "image/png", width: 1200, height: 400 }
    ]
  },
  {
    studioSlug: "tiny-orbit-forge",
    slug: "orbit-orchard",
    displayName: "Orbit Orchard",
    contentKind: "game",
    lifecycleStatus: "testing",
    visibility: "listed",
    isReported: true,
    currentMetadataRevision: 1,
    shortDescription: "Cultivate fruit rings around a tiny planet in zero gravity.",
    description:
      "Build spinning orchards, redirect sunlight, and juggle floating harvest bots in a bright orbital farming sandbox.",
    genreDisplay: "Simulation, Sandbox, Sci-Fi",
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "0.8.1",
    currentReleasePublishedAt: "2026-03-05T17:15:00Z",
    acquisition: {
      url: "https://tiny-orbit-forge.example/titles/orbit-orchard",
      label: "Open publisher page",
      providerDisplayName: "Tiny Orbit Forge Direct",
      providerHomepageUrl: "https://tiny-orbit-forge.example"
    },
    media: [
      { role: "card", assetPath: "orbit-orchard/card.png", altText: "Orbit Orchard card art", mimeType: "image/png", width: 900, height: 1280 },
      { role: "hero", assetPath: "orbit-orchard/hero.png", altText: "Orbit Orchard hero art", mimeType: "image/png", width: 1600, height: 900 },
      { role: "logo", assetPath: "orbit-orchard/logo.png", altText: "Orbit Orchard logo", mimeType: "image/png", width: 1200, height: 400 }
    ]
  }
];

export const localMigrationEnvironment: MigrationEnvironmentLayout = {
  appName: "board-enthusiasts-local",
  frontendBaseUrl: "http://127.0.0.1:4173",
  apiBaseUrl: "http://127.0.0.1:8787",
  supabaseProjectRef: "local-dev",
  supabaseUrl: "http://127.0.0.1:54321",
  supabaseAnonKeyVariable: "SUPABASE_ANON_KEY",
  supabaseServiceRoleKeyVariable: "SUPABASE_SERVICE_ROLE_KEY",
  supabaseMediaBucket: migrationMediaBucket
};

export const stagingMigrationEnvironment: MigrationEnvironmentLayout = {
  appName: "board-enthusiasts-staging",
  frontendBaseUrl: "https://staging.boardenthusiasts.com",
  apiBaseUrl: "https://api.staging.boardenthusiasts.com",
  supabaseProjectRef: "staging-project-ref",
  supabaseUrl: "https://<project-ref>.supabase.co",
  supabaseAnonKeyVariable: "SUPABASE_ANON_KEY",
  supabaseServiceRoleKeyVariable: "SUPABASE_SERVICE_ROLE_KEY",
  supabaseMediaBucket: migrationMediaBucket
};
