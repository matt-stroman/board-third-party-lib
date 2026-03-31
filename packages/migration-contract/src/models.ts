export interface MigrationEnvironmentLayout {
  appName: string;
  frontendBaseUrl: string;
  apiBaseUrl: string;
  supabaseProjectRef: string;
  supabaseUrl: string;
  supabasePublishableKeyVariable: string;
  supabaseSecretKeyVariable: string;
  supabaseMediaBucket: string;
}

export type PlatformRole =
  | "player"
  | "developer"
  | "verified_developer"
  | "moderator"
  | "admin"
  | "super_admin";

export type MarketingContactStatus = "subscribed" | "unsubscribed" | "bounced" | "suppressed" | "converted";
/**
 * Lifecycle stage of a landing-page marketing contact.
 */
export type MarketingContactLifecycleStatus = "waitlisted" | "invited" | "converted";
/**
 * Signup intent selected by a landing-page contact.
 */
export type MarketingContactRoleInterest = "player" | "developer";

export type StudioMembershipRole = "owner" | "admin" | "editor";
export type TitleContentKind = "game" | "app";
export type TitleLifecycleStatus = "draft" | "active" | "archived";
export type TitleVisibility = "unlisted" | "listed";
export type TitleMediaRole = "card" | "hero" | "logo";

export interface CurrentUserResponse {
  subject: string;
  displayName: string;
  email: string | null;
  emailVerified: boolean;
  identityProvider: string | null;
  roles: PlatformRole[];
  avatarUrl?: string | null;
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

export interface UpdateUserProfileRequest {
  displayName?: string | null;
  firstName?: string | null;
  lastName?: string | null;
  avatarUrl?: string | null;
  avatarDataUrl?: string | null;
}

export interface UserNameAvailability {
  requestedUserName: string;
  normalizedUserName: string;
  available: boolean;
}

export interface UserNameAvailabilityResponse {
  userNameAvailability: UserNameAvailability;
}

export interface MarketingSignupRequest {
  email: string;
  firstName?: string | null;
  source: string;
  consentTextVersion: string;
  turnstileToken?: string | null;
  /**
   * Optional role-interest selections captured from the landing-page waitlist form.
   */
  roleInterests?: MarketingContactRoleInterest[] | null;
  utmSource?: string | null;
  utmMedium?: string | null;
  utmCampaign?: string | null;
  utmTerm?: string | null;
  utmContent?: string | null;
}

export interface MarketingSignup {
  email: string;
  firstName: string | null;
  status: MarketingContactStatus;
  /**
   * Lifecycle state tracked for the waitlist contact.
   */
  lifecycleStatus: MarketingContactLifecycleStatus;
  /**
   * Normalized role-interest selections stored for the waitlist contact.
   */
  roleInterests: MarketingContactRoleInterest[];
  source: string;
  consentedAt: string;
  updatedAt: string;
}

export interface MarketingSignupResponse {
  accepted: boolean;
  duplicate: boolean;
  signup: MarketingSignup;
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

export interface UserNotification {
  id: string;
  category: string;
  title: string;
  body: string;
  actionUrl: string | null;
  isRead: boolean;
  readAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UserNotificationListResponse {
  notifications: UserNotification[];
}

export interface UserNotificationResponse {
  notification: UserNotification;
}

export interface PlayerTitleListResponse {
  titles: CatalogTitleSummary[];
}

export interface PlayerCollectionMutationResponse {
  titleId: string;
  included: boolean;
  alreadyInRequestedState: boolean;
}

export interface CreatePlayerTitleReportRequest {
  titleId: string;
  reason: string;
}

export interface PlayerTitleReportSummary {
  id: string;
  titleId: string;
  studioSlug: string;
  titleSlug: string;
  titleDisplayName: string;
  status: string;
  reason: string;
  createdAt: string;
  updatedAt: string;
}

export interface PlayerTitleReportListResponse {
  reports: PlayerTitleReportSummary[];
}

export interface PlayerTitleReportResponse {
  report: PlayerTitleReportSummary;
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

export interface TitleReportActor {
  subject: string;
  userName: string | null;
  displayName: string | null;
  email: string | null;
}

export interface TitleReportMessage {
  id: string;
  authorSubject: string;
  authorUserName: string | null;
  authorDisplayName: string | null;
  authorEmail: string | null;
  authorRole: string;
  audience: string;
  message: string;
  createdAt: string;
}

export interface TitleReportSummary {
  id: string;
  titleId: string;
  studioId: string;
  studioSlug: string;
  studioDisplayName: string;
  titleSlug: string;
  titleDisplayName: string;
  titleShortDescription: string;
  genreDisplay: string;
  currentMetadataRevision: number;
  reporterSubject: string;
  reporterUserName: string | null;
  reporterDisplayName: string | null;
  reporterEmail: string | null;
  status: string;
  reason: string;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
  messageCount: number;
}

export interface TitleReportDetail {
  report: TitleReportSummary;
  resolutionNote: string | null;
  resolvedBy: TitleReportActor | null;
  messages: TitleReportMessage[];
}

export interface TitleReportListResponse {
  reports: TitleReportSummary[];
}

export interface TitleReportDetailResponse {
  report: TitleReportDetail;
}

export interface AddTitleReportMessageRequest {
  message: string;
}

export interface AddModerationTitleReportMessageRequest {
  message: string;
  recipientRole: "player" | "developer";
}

export interface ModerateTitleReportDecisionRequest {
  note: string | null;
}

export interface BoardProfile {
  boardUserId: string;
  displayName: string;
  avatarUrl: string | null;
  linkedAt: string;
  lastSyncedAt: string;
}

export interface BoardProfileResponse {
  boardProfile: BoardProfile;
}

export interface UpsertBoardProfileRequest {
  boardUserId: string;
  displayName: string | null;
  avatarUrl: string | null;
  lastSyncedAt?: string | null;
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
  avatarUrl: string | null;
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

export interface DeveloperTitleListResponse {
  titles: CatalogTitleSummary[];
}

export interface GenreDefinition {
  slug: string;
  displayName: string;
}

export interface GenreListResponse {
  genres: GenreDefinition[];
}

export interface AgeRatingAuthorityDefinition {
  code: string;
  displayName: string;
}

export interface AgeRatingAuthorityListResponse {
  ageRatingAuthorities: AgeRatingAuthorityDefinition[];
}

export interface UpsertTitleMetadataRequest {
  displayName: string;
  shortDescription: string;
  description: string;
  genreSlugs: string[];
  minPlayers: number;
  maxPlayers: number;
  ageRatingAuthority: string;
  ageRatingValue: string;
  minAgeYears: number;
}

export interface CreateDeveloperTitleRequest {
  contentKind: TitleContentKind;
  metadata: UpsertTitleMetadataRequest;
}

export interface UpdateDeveloperTitleRequest {
  contentKind: TitleContentKind;
  visibility: TitleVisibility;
}

export interface DeleteDeveloperTitleRequest {
  currentPassword: string;
  confirmationTitleName: string;
}

export interface VerifyCurrentUserPasswordRequest {
  currentPassword: string;
}

export interface VerifyCurrentUserPasswordResponse {
  verified: true;
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

export interface TitleMediaAssetListResponse {
  mediaAssets: TitleMediaAsset[];
}

export interface TitleMediaAssetResponse {
  mediaAsset: TitleMediaAsset;
}

export interface UpsertTitleMediaAssetRequest {
  sourceUrl: string;
  altText: string | null;
  mimeType: string | null;
  width: number | null;
  height: number | null;
}

export interface CurrentTitleRelease {
  id: string;
  version: string;
  publishedAt: string;
}

export interface DeveloperTitle {
  id: string;
  studioId: string;
  studioSlug: string;
  slug: string;
  contentKind: TitleContentKind;
  lifecycleStatus: TitleLifecycleStatus;
  visibility: TitleVisibility;
  currentMetadataRevision: number;
  displayName: string;
  shortDescription: string;
  description: string | null;
  genreSlugs: string[];
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
  mediaAssets: TitleMediaAsset[];
  currentRelease?: CurrentTitleRelease;
  acquisition?: PublicTitleAcquisition;
  currentReleaseId: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface DeveloperTitleResponse {
  title: DeveloperTitle;
}

export interface TitleMetadataVersion {
  revisionNumber: number;
  isCurrent: boolean;
  isFrozen: boolean;
  displayName: string;
  shortDescription: string;
  description: string;
  genreSlugs: string[];
  genreDisplay: string;
  minPlayers: number;
  maxPlayers: number;
  playerCountDisplay: string;
  ageRatingAuthority: string;
  ageRatingValue: string;
  minAgeYears: number;
  ageDisplay: string;
  createdAt: string;
  updatedAt: string;
}

export interface TitleMetadataVersionListResponse {
  metadataVersions: TitleMetadataVersion[];
}

export type TitleReleaseStatus = "testing" | "production";

export interface UpsertTitleReleaseRequest {
  version: string;
  status: TitleReleaseStatus;
  acquisitionUrl: string | null;
}

export interface TitleRelease {
  id: string;
  version: string;
  status: TitleReleaseStatus;
  acquisitionUrl: string | null;
  isCurrent: boolean;
  publishedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface TitleReleaseListResponse {
  releases: TitleRelease[];
}

export interface TitleReleaseResponse {
  release: TitleRelease;
}

export interface PublicTitleAcquisition {
  url: string;
}

export interface CatalogTitleSummary {
  id: string;
  studioId: string;
  studioSlug: string;
  studioDisplayName: string;
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
  logoImageUrl: string | null;
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

export interface CatalogTitleListQuery {
  pageNumber?: number;
  pageSize?: number;
  studioSlug?: string | string[];
  genre?: string | string[];
  contentKind?: TitleContentKind;
  search?: string;
  minPlayers?: number;
  maxPlayers?: number;
  sort?:
    | "title-asc"
    | "title-desc"
    | "studio-asc"
    | "studio-desc"
    | "genre-asc"
    | "players-asc"
    | "players-desc"
    | "age-asc"
    | "age-desc";
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
  avatarAssetPath: string;
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
  genreSlugs: string[];
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
export const migrationMediaBuckets = {
  avatars: "avatars",
  cardImages: "card-images",
  heroImages: "hero-images",
  logoImages: "logo-images",
} as const;

export type MigrationMediaBucketKey = keyof typeof migrationMediaBuckets;
export type MigrationMediaBucketName = (typeof migrationMediaBuckets)[MigrationMediaBucketKey];
export type MigrationMediaUploadPolicy = {
  readonly bucket: MigrationMediaBucketName;
  readonly maxUploadBytes: number;
  readonly acceptedMimeTypes: readonly string[];
  readonly recommendedWidth: number;
  readonly recommendedHeight: number;
};

export const migrationMediaUploadPolicies = {
  avatars: {
    bucket: migrationMediaBuckets.avatars,
    maxUploadBytes: 256 * 1024,
    acceptedMimeTypes: ["image/webp", "image/jpeg", "image/png"],
    recommendedWidth: 512,
    recommendedHeight: 512,
  },
  cardImages: {
    bucket: migrationMediaBuckets.cardImages,
    maxUploadBytes: 1536 * 1024,
    acceptedMimeTypes: ["image/webp", "image/jpeg", "image/png"],
    recommendedWidth: 900,
    recommendedHeight: 1280,
  },
  heroImages: {
    bucket: migrationMediaBuckets.heroImages,
    maxUploadBytes: 3 * 1024 * 1024,
    acceptedMimeTypes: ["image/webp", "image/jpeg", "image/png", "image/svg+xml"],
    recommendedWidth: 1600,
    recommendedHeight: 900,
  },
  logoImages: {
    bucket: migrationMediaBuckets.logoImages,
    maxUploadBytes: 256 * 1024,
    acceptedMimeTypes: ["image/webp", "image/png", "image/svg+xml"],
    recommendedWidth: 1200,
    recommendedHeight: 400,
  },
} as const satisfies Record<MigrationMediaBucketKey, MigrationMediaUploadPolicy>;

const migrationSeedStudioDescriptionMaxLength = 1600;
const migrationSeedTitleShortDescriptionMaxLength = 220;
const migrationSeedTitleDescriptionMaxLength = 1600;

export const maintainedGenres: ReadonlyArray<GenreDefinition> = [
  { slug: "adventure", displayName: "Adventure" },
  { slug: "arcade", displayName: "Arcade" },
  { slug: "cozy", displayName: "Cozy" },
  { slug: "collection", displayName: "Collection" },
  { slug: "co-op", displayName: "Co-op" },
  { slug: "community", displayName: "Community" },
  { slug: "companion", displayName: "Companion" },
  { slug: "competitive", displayName: "Competitive" },
  { slug: "crafting", displayName: "Crafting" },
  { slug: "creative", displayName: "Creative" },
  { slug: "dashboard", displayName: "Dashboard" },
  { slug: "delivery", displayName: "Delivery" },
  { slug: "exploration", displayName: "Exploration" },
  { slug: "family", displayName: "Family" },
  { slug: "festival", displayName: "Festival" },
  { slug: "harbor", displayName: "Harbor" },
  { slug: "management", displayName: "Management" },
  { slug: "planning", displayName: "Planning" },
  { slug: "platforming", displayName: "Platforming" },
  { slug: "puzzle", displayName: "Puzzle" },
  { slug: "qa", displayName: "QA" },
  { slug: "racing", displayName: "Racing" },
  { slug: "relaxing", displayName: "Relaxing" },
  { slug: "sandbox", displayName: "Sandbox" },
  { slug: "sci-fi", displayName: "Sci-Fi" },
  { slug: "simulation", displayName: "Simulation" },
  { slug: "strategy", displayName: "Strategy" },
  { slug: "survival", displayName: "Survival" },
  { slug: "tactics", displayName: "Tactics" },
  { slug: "travel", displayName: "Travel" },
  { slug: "utility", displayName: "Utility" },
  { slug: "workshop", displayName: "Workshop" }
];

export const maintainedAgeRatingAuthorities: ReadonlyArray<AgeRatingAuthorityDefinition> = [
  { code: "ESRB", displayName: "ESRB" },
  { code: "PEGI", displayName: "PEGI" },
  { code: "USK", displayName: "USK" },
  { code: "CERO", displayName: "CERO" },
  { code: "ACB", displayName: "ACB" }
];

const maintainedGenreMap = new Map(maintainedGenres.map((genre) => [genre.slug, genre]));
const maintainedAgeRatingAuthorityMap = new Map(maintainedAgeRatingAuthorities.map((authority) => [authority.code, authority]));

export function normalizeGenreSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
}

export function getGenreDefinition(genreSlug: string): GenreDefinition | undefined {
  return maintainedGenreMap.get(normalizeGenreSlug(genreSlug));
}

export function getAgeRatingAuthorityDefinition(authorityCode: string): AgeRatingAuthorityDefinition | undefined {
  return maintainedAgeRatingAuthorityMap.get(authorityCode.trim().toUpperCase());
}

export function buildGenreDisplay(genreSlugs: readonly string[]): string {
  return genreSlugs
    .map((genreSlug) => getGenreDefinition(genreSlug)?.displayName ?? genreSlug)
    .join(", ");
}

function trimToWordBoundary(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value.trim();
  }

  const slice = value.slice(0, maxLength + 1);
  const lastSpace = slice.lastIndexOf(" ");
  return (lastSpace > 0 ? slice.slice(0, lastSpace) : slice.slice(0, maxLength)).trim();
}

function buildNearLimitCopy(segments: readonly string[], maxLength: number, reserve = 24): string {
  const cleanedSegments = segments.map((segment) => segment.trim()).filter(Boolean);
  let value = cleanedSegments.join(" ");
  const targetLength = Math.max(1, maxLength - reserve);

  if (value.length >= targetLength) {
    return trimToWordBoundary(value, maxLength);
  }

  let index = 0;
  while (value.length < targetLength) {
    value = `${value} ${cleanedSegments[index % cleanedSegments.length]}`.trim();
    index += 1;
  }

  return trimToWordBoundary(value, maxLength);
}

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
  },
  {
    userName: "mason.lee",
    email: "mason.lee@boardtpl.local",
    displayName: "Mason Lee",
    firstName: "Mason",
    lastName: "Lee",
    roles: ["player", "moderator"]
  },
  {
    userName: "noah.kim",
    email: "noah.kim@boardtpl.local",
    displayName: "Noah Kim",
    firstName: "Noah",
    lastName: "Kim",
    roles: ["player", "developer", "verified_developer"],
    boardUserId: "board_noah_kim",
    boardAvatarUrl: "https://cdn.board.fun/avatars/board_noah_kim.png"
  },
  {
    userName: "sophia.patel",
    email: "sophia.patel@boardtpl.local",
    displayName: "Sophia Patel",
    firstName: "Sophia",
    lastName: "Patel",
    roles: ["player", "developer"]
  },
  {
    userName: "liam.chen",
    email: "liam.chen@boardtpl.local",
    displayName: "Liam Chen",
    firstName: "Liam",
    lastName: "Chen",
    roles: ["player", "developer"]
  },
  {
    userName: "mia.robinson",
    email: "mia.robinson@boardtpl.local",
    displayName: "Mia Robinson",
    firstName: "Mia",
    lastName: "Robinson",
    roles: ["player", "developer"]
  },
  {
    userName: "ethan.walker",
    email: "ethan.walker@boardtpl.local",
    displayName: "Ethan Walker",
    firstName: "Ethan",
    lastName: "Walker",
    roles: ["player"]
  },
  {
    userName: "grace.nguyen",
    email: "grace.nguyen@boardtpl.local",
    displayName: "Grace Nguyen",
    firstName: "Grace",
    lastName: "Nguyen",
    roles: ["player"]
  },
  {
    userName: "lucas.reed",
    email: "lucas.reed@boardtpl.local",
    displayName: "Lucas Reed",
    firstName: "Lucas",
    lastName: "Reed",
    roles: ["player"]
  },
  {
    userName: "zoe.bennett",
    email: "zoe.bennett@boardtpl.local",
    displayName: "Zoe Bennett",
    firstName: "Zoe",
    lastName: "Bennett",
    roles: ["player"]
  },
  {
    userName: "caleb.foster",
    email: "caleb.foster@boardtpl.local",
    displayName: "Caleb Foster",
    firstName: "Caleb",
    lastName: "Foster",
    roles: ["player"]
  },
  {
    userName: "harper.diaz",
    email: "harper.diaz@boardtpl.local",
    displayName: "Harper Diaz",
    firstName: "Harper",
    lastName: "Diaz",
    roles: ["player"]
  },
  {
    userName: "henry.brooks",
    email: "henry.brooks@boardtpl.local",
    displayName: "Henry Brooks",
    firstName: "Henry",
    lastName: "Brooks",
    roles: ["player"]
  },
  {
    userName: "natalie.price",
    email: "natalie.price@boardtpl.local",
    displayName: "Natalie Price",
    firstName: "Natalie",
    lastName: "Price",
    roles: ["player"]
  },
  {
    userName: "owen.hughes",
    email: "owen.hughes@boardtpl.local",
    displayName: "Owen Hughes",
    firstName: "Owen",
    lastName: "Hughes",
    roles: ["player"]
  },
  {
    userName: "chloe.sanders",
    email: "chloe.sanders@boardtpl.local",
    displayName: "Chloe Sanders",
    firstName: "Chloe",
    lastName: "Sanders",
    roles: ["player"]
  },
  {
    userName: "jack.cooper",
    email: "jack.cooper@boardtpl.local",
    displayName: "Jack Cooper",
    firstName: "Jack",
    lastName: "Cooper",
    roles: ["player"]
  },
  {
    userName: "ella.morgan",
    email: "ella.morgan@boardtpl.local",
    displayName: "Ella Morgan",
    firstName: "Ella",
    lastName: "Morgan",
    roles: ["player"]
  },
  {
    userName: "aiden.scott",
    email: "aiden.scott@boardtpl.local",
    displayName: "Aiden Scott",
    firstName: "Aiden",
    lastName: "Scott",
    roles: ["player"]
  },
  {
    userName: "ruby.ward",
    email: "ruby.ward@boardtpl.local",
    displayName: "Ruby Ward",
    firstName: "Ruby",
    lastName: "Ward",
    roles: ["player"]
  },
  {
    userName: "isaac.flores",
    email: "isaac.flores@boardtpl.local",
    displayName: "Isaac Flores",
    firstName: "Isaac",
    lastName: "Flores",
    roles: ["player"]
  }
];

function buildSeedStudioFixture(
  slug: string,
  displayName: string,
  description: string,
  ownerUserName: string
): MigrationSeedStudioFixture {
  const studioHandle = displayName.replace(/[^A-Za-z0-9]/g, "");
  const longDescription = buildNearLimitCopy(
    [
      description,
      `${displayName} builds polished releases for Board with a strong emphasis on clear onboarding, family-friendly session flow, and readable interfaces across both handheld and docked play.`,
      `The studio profile usually highlights recent launches, roadmap visibility, support channels, and public-facing brand assets because players, moderators, and partner developers all rely on the same listing.`,
      `Local seed data should reflect realistic publishing expectations, including long-form descriptions, multiple links, and enough editorial detail to expose layout issues before UI changes reach production.`,
      `Each seeded studio description is intentionally dense so overview cards, browse panels, and developer workspace summaries have to deal with real content volume instead of placeholder blurbs.`
    ],
    migrationSeedStudioDescriptionMaxLength
  );
  return {
    slug,
    displayName,
    description: longDescription,
    ownerUserName,
    links: [
      { label: "Website", url: `https://${slug}.example` },
      { label: "Support", url: `https://${slug}.example/support` },
      { label: "Discord", url: `https://discord.gg/${slug.replace(/-/g, "")}` },
      { label: "YouTube", url: `https://www.youtube.com/@${studioHandle}` }
    ],
    avatarAssetPath: `studios/${slug}/logo.svg`,
    logoAssetPath: `studios/${slug}/logo.svg`,
    bannerAssetPath: `studios/${slug}/banner.svg`
  };
}

function buildSeedTitleFixture(args: {
  studioSlug: string;
  studioDisplayName: string;
  slug: string;
  displayName: string;
  contentKind: TitleContentKind;
  lifecycleStatus: TitleLifecycleStatus;
  isReported?: boolean;
  currentMetadataRevision?: number;
  shortDescription: string;
  description: string;
  genreSlugs: string[];
  minPlayers: number;
  maxPlayers: number;
  ageRatingAuthority: string;
  ageRatingValue: string;
  minAgeYears: number;
  currentReleaseVersion?: string;
  currentReleasePublishedAt?: string;
}): MigrationSeedTitleFixture {
  const studioHomepage = `https://${args.studioSlug}.example`;
  const longShortDescription = buildNearLimitCopy(
    [
      args.shortDescription,
      `${args.displayName} is tuned for Board players who expect a polished listing, clear install context, and enough summary detail to decide whether the current release fits their group.`,
      `The short description is intentionally close to the real constraint so cards, quick views, and workspace summaries must handle a dense but still readable pitch.`
    ],
    migrationSeedTitleShortDescriptionMaxLength,
    12
  );
  const longDescription = buildNearLimitCopy(
    [
      args.description,
      `${args.displayName} is seeded with production-style metadata so the local stack has to render full editorial copy, stronger acquisition context, and more realistic release framing for both players and developers.`,
      `The description intentionally covers onboarding expectations, core interaction loops, accessibility and family-use considerations, replay value, and the sort of operational detail a real studio would maintain during ongoing release management.`,
      `This fixture text is long on purpose: it helps surface weak panel sizing, awkward column splits, truncated cards, and any workflow screens that only looked correct when fed placeholder content.`
    ],
    migrationSeedTitleDescriptionMaxLength
  );
  return {
    studioSlug: args.studioSlug,
    slug: args.slug,
    displayName: args.displayName,
    contentKind: args.contentKind,
    lifecycleStatus: args.lifecycleStatus,
    visibility: "listed",
    isReported: args.isReported ?? false,
    currentMetadataRevision: args.currentMetadataRevision ?? 1,
    shortDescription: longShortDescription,
    description: longDescription,
    genreSlugs: args.genreSlugs,
    genreDisplay: buildGenreDisplay(args.genreSlugs),
    minPlayers: args.minPlayers,
    maxPlayers: args.maxPlayers,
    ageRatingAuthority: args.ageRatingAuthority,
    ageRatingValue: args.ageRatingValue,
    minAgeYears: args.minAgeYears,
    currentReleaseVersion: args.currentReleaseVersion,
    currentReleasePublishedAt: args.currentReleasePublishedAt,
    acquisition: {
      url: `${studioHomepage}/titles/${args.slug}`
    },
    media: [
      { role: "card", assetPath: `${args.slug}/card.png`, altText: `${args.displayName} card art`, mimeType: "image/png", width: 900, height: 1280 },
      { role: "hero", assetPath: `${args.slug}/hero.png`, altText: `${args.displayName} hero art`, mimeType: "image/png", width: 1600, height: 900 },
      { role: "logo", assetPath: `${args.slug}/logo.png`, altText: `${args.displayName} logo`, mimeType: "image/png", width: 1200, height: 400 }
    ]
  };
}

export const migrationSeedStudios: ReadonlyArray<MigrationSeedStudioFixture> = [
  buildSeedStudioFixture("blue-harbor-games", "Blue Harbor Games", "Co-op adventures with bright maritime themes and approachable controls.", "emma.torres"),
  buildSeedStudioFixture("tiny-orbit-forge", "Tiny Orbit Forge", "Sci-fi builders featuring modular crafting and community challenges.", "olivia.bennett"),
  buildSeedStudioFixture("copper-finch-works", "Copper Finch Works", "Mechanical puzzlers and workshop sims with tactile interfaces.", "noah.kim"),
  buildSeedStudioFixture("harborlight-mechanics", "Harborlight Mechanics", "Utility-driven support apps and polished tabletop helpers.", "sophia.patel"),
  buildSeedStudioFixture("lumen-cartography", "Lumen Cartography", "Exploration tools and narrative route-planning experiences.", "liam.chen"),
  buildSeedStudioFixture("moss-byte-collective", "Moss Byte Collective", "Relaxed strategy titles and soft-tech companion software.", "mia.robinson"),
  buildSeedStudioFixture("north-maple-interactive", "North Maple Interactive", "Accessible family releases with travel, festival, and builder themes.", "emma.torres"),
  buildSeedStudioFixture("pine-lantern-labs", "Pine Lantern Labs", "Color-rich creative games with social and couch-friendly loops.", "olivia.bennett"),
  buildSeedStudioFixture("quartz-rabbit-studio", "Quartz Rabbit Studio", "Fast-paced arcade and tactics projects with high-contrast UI.", "noah.kim")
];

export const migrationSeedTitles: ReadonlyArray<MigrationSeedTitleFixture> = [
  buildSeedTitleFixture({
    studioSlug: "blue-harbor-games",
    studioDisplayName: "Blue Harbor Games",
    slug: "lantern-drift",
    displayName: "Lantern Drift",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 2,
    shortDescription: "Guide glowing paper boats through a midnight canal festival without snuffing the flame.",
    description: "Tilt waterways, spin lock-gates, and weave through fireworks as every lantern casts new puzzle shadows across the river. Developed by Blue Harbor Games.",
    genreSlugs: ["puzzle", "family"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.0",
    currentReleasePublishedAt: "2026-03-07T12:00:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "blue-harbor-games",
    studioDisplayName: "Blue Harbor Games",
    slug: "compass-echo",
    displayName: "Compass Echo",
    contentKind: "app",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Plot expedition routes, track secrets, and sync clue boards for sprawling adventures.",
    description: "Compass Echo is a premium companion app for campaign nights, with layered maps, route planning, and clue pinning for cooperative exploration games.",
    genreSlugs: ["companion", "utility", "exploration"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "0.9.0",
    currentReleasePublishedAt: "2026-03-06T18:30:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "blue-harbor-games",
    studioDisplayName: "Blue Harbor Games",
    slug: "riverlight-quest",
    displayName: "Riverlight Quest",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 2,
    shortDescription: "Chart branching raft routes and cooperative rescues through glowing canyon waterways.",
    description: "Crew a lantern raft, barter with riverside towns, and coordinate rescue missions as currents shift every round.",
    genreSlugs: ["adventure", "family", "exploration"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "1.2.0",
    currentReleasePublishedAt: "2026-03-04T16:00:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "blue-harbor-games",
    studioDisplayName: "Blue Harbor Games",
    slug: "parade-of-sparks",
    displayName: "Parade of Sparks",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Build synchronized float routes and light shows for a citywide midnight celebration.",
    description: "Balance timing, crowd flow, and fireworks cues in a polished festival-management puzzler designed for short sessions.",
    genreSlugs: ["strategy", "festival", "family"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "0.7.3",
    currentReleasePublishedAt: "2026-03-03T20:20:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "tiny-orbit-forge",
    studioDisplayName: "Tiny Orbit Forge",
    slug: "orbit-orchard",
    displayName: "Orbit Orchard",
    contentKind: "game",
    lifecycleStatus: "active",
    isReported: true,
    currentMetadataRevision: 1,
    shortDescription: "Cultivate fruit rings around a tiny planet in zero gravity.",
    description: "Build spinning orchards, redirect sunlight, and juggle floating harvest bots in a bright orbital farming sandbox.",
    genreSlugs: ["simulation", "sandbox", "sci-fi"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "0.8.1",
    currentReleasePublishedAt: "2026-03-05T17:15:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "tiny-orbit-forge",
    studioDisplayName: "Tiny Orbit Forge",
    slug: "nebula-relay",
    displayName: "Nebula Relay",
    contentKind: "app",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Coordinate community tournaments, relay schedules, and match alerts from a single dashboard.",
    description: "A tournament companion app for leagues and local clubs, with bracket snapshots and player-ready event reminders.",
    genreSlugs: ["utility", "community", "sci-fi"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.1.0",
    currentReleasePublishedAt: "2026-03-02T14:45:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "tiny-orbit-forge",
    studioDisplayName: "Tiny Orbit Forge",
    slug: "solar-orchard",
    displayName: "Solar Orchard",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Arrange reflective gardens and solar collectors across a drifting farm colony.",
    description: "Optimize heat, water, and pollination paths in a calm orbital builder with family-friendly pacing.",
    genreSlugs: ["simulation", "strategy", "sci-fi"],
    minPlayers: 1,
    maxPlayers: 3,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.4",
    currentReleasePublishedAt: "2026-03-01T10:10:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "tiny-orbit-forge",
    studioDisplayName: "Tiny Orbit Forge",
    slug: "starlane-sprint",
    displayName: "Starlane Sprint",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Race modular courier craft through shifting asteroid lanes and signal gates.",
    description: "Short competitive runs, upgrade drafting, and bright orbital hazards make this a strong arcade anchor for local sessions.",
    genreSlugs: ["arcade", "racing", "sci-fi"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "0.6.5",
    currentReleasePublishedAt: "2026-02-28T22:00:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "copper-finch-works",
    studioDisplayName: "Copper Finch Works",
    slug: "clockwork-crew",
    displayName: "Clockwork Crew",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Direct a tiny team of workshop automatons through timed repair shifts.",
    description: "Assign clockwork specialists, reroute belts, and keep every bench moving in a compact strategy sim.",
    genreSlugs: ["strategy", "simulation", "workshop"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "1.0.1",
    currentReleasePublishedAt: "2026-02-27T18:00:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "copper-finch-works",
    studioDisplayName: "Copper Finch Works",
    slug: "patchwork-port",
    displayName: "Patchwork Port",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Balance incoming cargo, repairs, and ferry traffic in a stitched-together harbor town.",
    description: "A cozy logistics game where every dock, crane, and repair queue becomes part of a larger port puzzle.",
    genreSlugs: ["management", "strategy", "harbor"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "0.9.2",
    currentReleasePublishedAt: "2026-02-26T11:15:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "harborlight-mechanics",
    studioDisplayName: "Harborlight Mechanics",
    slug: "signal-harbor",
    displayName: "Signal Harbor",
    contentKind: "app",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Monitor fleet status, player sessions, and maintenance notices from a polished dockside dashboard.",
    description: "A support utility for clubs and event hosts that keeps installation notes, room rosters, and service advisories in one place.",
    genreSlugs: ["utility", "dashboard", "community"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.3.0",
    currentReleasePublishedAt: "2026-02-25T09:30:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "harborlight-mechanics",
    studioDisplayName: "Harborlight Mechanics",
    slug: "cinderline-workshop",
    displayName: "Cinderline Workshop",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Restore traveling maker caravans and rebuild gear trains before the next market stop.",
    description: "Part repair sim and part organization puzzle, with approachable systems and strong tactile feedback.",
    genreSlugs: ["workshop", "puzzle", "crafting"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.2",
    currentReleasePublishedAt: "2026-02-24T15:40:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "lumen-cartography",
    studioDisplayName: "Lumen Cartography",
    slug: "anchorpoint-atlas",
    displayName: "Anchorpoint Atlas",
    contentKind: "app",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Bookmark routes, landmarks, and encounter notes for sprawling campaigns.",
    description: "A map-first companion app that helps players pin clues, annotate landmarks, and revisit branching travel paths.",
    genreSlugs: ["companion", "exploration", "utility"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.0",
    currentReleasePublishedAt: "2026-02-23T12:30:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "lumen-cartography",
    studioDisplayName: "Lumen Cartography",
    slug: "trailblazer-terminal",
    displayName: "Trailblazer Terminal",
    contentKind: "app",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Plan branching expeditions, expedition kits, and route briefings from one terminal view.",
    description: "Mission planning, route handoff, and shared gear checklists make this a strong co-op planning tool for local groups.",
    genreSlugs: ["utility", "planning", "exploration"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "0.8.8",
    currentReleasePublishedAt: "2026-02-22T08:20:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "moss-byte-collective",
    studioDisplayName: "Moss Byte Collective",
    slug: "cobalt-almanac",
    displayName: "Cobalt Almanac",
    contentKind: "app",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Collect creature notes, recipe experiments, and seasonal discoveries in a shared almanac.",
    description: "A relaxed utility for long-running family saves, with illustrated journals and easy sharing between profiles.",
    genreSlugs: ["companion", "collection", "family"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.6",
    currentReleasePublishedAt: "2026-02-21T19:50:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "moss-byte-collective",
    studioDisplayName: "Moss Byte Collective",
    slug: "hearthside-protocol",
    displayName: "Hearthside Protocol",
    contentKind: "game",
    lifecycleStatus: "active",
    isReported: true,
    currentMetadataRevision: 1,
    shortDescription: "Protect a woodland settlement by balancing warmth, food, and quiet machine helpers.",
    description: "A gentle survival-management game built around cozy routines, automation chains, and small-scale strategy.",
    genreSlugs: ["strategy", "survival", "cozy"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "0.9.4",
    currentReleasePublishedAt: "2026-02-20T13:10:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "north-maple-interactive",
    studioDisplayName: "North Maple Interactive",
    slug: "beacon-boardwalk",
    displayName: "Beacon Boardwalk",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Restore a weathered shoreline promenade through mini-games and family quests.",
    description: "Reopen arcades, rebuild attractions, and guide visitors through a bright seasonal boardwalk full of small objectives.",
    genreSlugs: ["family", "adventure", "festival"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.1.3",
    currentReleasePublishedAt: "2026-02-19T16:45:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "north-maple-interactive",
    studioDisplayName: "North Maple Interactive",
    slug: "marble-meridian",
    displayName: "Marble Meridian",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Roll magnetic marbles through shifting global landmarks and route gates.",
    description: "A brisk family puzzler about momentum, shortcuts, and map-based contraptions with quick rematch appeal.",
    genreSlugs: ["puzzle", "family", "travel"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "1.0.8",
    currentReleasePublishedAt: "2026-02-18T10:25:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "pine-lantern-labs",
    studioDisplayName: "Pine Lantern Labs",
    slug: "mosaic-drift",
    displayName: "Mosaic Drift",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Compose drifting tile murals while matching wind, color, and crowd patterns.",
    description: "A meditative score-chase game built around layered tiles, pattern chains, and soft visual feedback.",
    genreSlugs: ["puzzle", "creative", "relaxing"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E",
    minAgeYears: 6,
    currentReleaseVersion: "0.9.1",
    currentReleasePublishedAt: "2026-02-17T21:05:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "pine-lantern-labs",
    studioDisplayName: "Pine Lantern Labs",
    slug: "festival-foundry",
    displayName: "Festival Foundry",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Design parade props, light rigs, and celebration routes for a cooperative city showcase.",
    description: "Mix crafting, staging, and short tactical planning in a lively builder tuned for couch co-op.",
    genreSlugs: ["creative", "strategy", "festival"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "1.0.0",
    currentReleasePublishedAt: "2026-02-16T18:55:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "quartz-rabbit-studio",
    studioDisplayName: "Quartz Rabbit Studio",
    slug: "nightglass-tactics",
    displayName: "Nightglass Tactics",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Outmaneuver rival squads through mirrored corridors and breakable glass sightlines.",
    description: "A compact tactics game with fast rounds, crisp silhouettes, and approachable but rewarding positioning rules.",
    genreSlugs: ["tactics", "strategy", "competitive"],
    minPlayers: 1,
    maxPlayers: 2,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "1.2.1",
    currentReleasePublishedAt: "2026-02-15T12:00:00Z"
  }),
  buildSeedTitleFixture({
    studioSlug: "quartz-rabbit-studio",
    studioDisplayName: "Quartz Rabbit Studio",
    slug: "cascade-courier",
    displayName: "Cascade Courier",
    contentKind: "game",
    lifecycleStatus: "active",
    currentMetadataRevision: 1,
    shortDescription: "Leap delivery gliders across canyon waterfalls under tight dispatch windows.",
    description: "An arcade courier game about momentum, drop accuracy, and route memory, with a strong speedrun loop.",
    genreSlugs: ["arcade", "platforming", "delivery"],
    minPlayers: 1,
    maxPlayers: 1,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
    currentReleaseVersion: "0.8.4",
    currentReleasePublishedAt: "2026-02-14T17:35:00Z"
  })
];

export const localMigrationEnvironment: MigrationEnvironmentLayout = {
  appName: "board-enthusiasts-local",
  frontendBaseUrl: "http://127.0.0.1:4173",
  apiBaseUrl: "http://127.0.0.1:8787",
  supabaseProjectRef: "local-dev",
  supabaseUrl: "http://127.0.0.1:55421",
  supabasePublishableKeyVariable: "SUPABASE_PUBLISHABLE_KEY",
  supabaseSecretKeyVariable: "SUPABASE_SECRET_KEY",
  supabaseMediaBucket: migrationMediaBucket
};

export const stagingMigrationEnvironment: MigrationEnvironmentLayout = {
  appName: "board-enthusiasts-staging",
  frontendBaseUrl: "https://staging.boardenthusiasts.com",
  apiBaseUrl: "https://api.staging.boardenthusiasts.com",
  supabaseProjectRef: "staging-project-ref",
  supabaseUrl: "https://<project-ref>.supabase.co",
  supabasePublishableKeyVariable: "SUPABASE_PUBLISHABLE_KEY",
  supabaseSecretKeyVariable: "SUPABASE_SECRET_KEY",
  supabaseMediaBucket: migrationMediaBucket
};
