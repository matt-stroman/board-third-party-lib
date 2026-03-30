import { maintainedApiRoutes } from "../../packages/migration-contract/src/index";

const baseUrl = (process.env.CONTRACT_SMOKE_BASE_URL ?? "https://localhost:7085").replace(/\/$/, "");
const fallbackToken = (process.env.CONTRACT_SMOKE_TOKEN ?? "").trim();
const playerToken = (process.env.CONTRACT_SMOKE_PLAYER_TOKEN ?? "").trim();
const developerToken = (process.env.CONTRACT_SMOKE_DEVELOPER_TOKEN ?? "").trim();
const moderatorToken = (process.env.CONTRACT_SMOKE_MODERATOR_TOKEN ?? "").trim();
const pngPixel = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9pX6N6gAAAAASUVORK5CYII="),
  (character) => character.charCodeAt(0),
);

interface SmokeResult {
  route: string;
  status: number;
  ok: boolean;
  detail: string;
}

interface SmokeContext {
  publicTitleId: string;
  managedStudioId: string;
  managedStudioSlug: string;
  managedStudioDisplayName: string;
  managedStudioDescription: string | null;
  managedTitleId: string;
  managedTitleMetadataRevision: number;
  currentUserNotificationId: string;
  createdStudioId: string;
  createdStudioSlug: string;
  createdTitleId: string;
  createdTitleSlug: string;
  createdTitleMetadataRevision: number;
  createdStudioLinkId: string;
  createdPlayerReportId: string;
  developerReportId: string;
  moderatedDeveloperSubject: string;
  moderatedValidateReportId: string;
  moderatedInvalidateReportId: string;
  releaseUnderTestId: string;
}

interface RequestPlan {
  path: string;
  init: RequestInit;
}

type JsonRecord = Record<string, unknown>;

function getRouteToken(access: (typeof maintainedApiRoutes)[number]["access"]): string {
  if (access === "public") {
    return "";
  }

  if (access === "moderator") {
    return moderatorToken || fallbackToken;
  }

  if (access === "developer") {
    return developerToken || playerToken || fallbackToken;
  }

  return playerToken || developerToken || moderatorToken || fallbackToken;
}

function buildHeaders(token: string, contentType?: string): Headers {
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (contentType) {
    headers.set("content-type", contentType);
  }
  return headers;
}

async function fetchRoute(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${baseUrl}${path}`, init);
}

async function readJson<T>(response: Response): Promise<T | undefined> {
  if (response.status === 204) {
    return undefined;
  }

  const text = await response.text();
  if (!text.trim()) {
    return undefined;
  }

  return JSON.parse(text) as T;
}

function requireValue(value: string | undefined, description: string): string {
  if (!value) {
    throw new Error(`Missing required smoke context value: ${description}`);
  }

  return value;
}

function requireNumber(value: number | undefined, description: string): number {
  if (value === undefined || Number.isNaN(value)) {
    throw new Error(`Missing required smoke context number: ${description}`);
  }

  return value;
}

async function fetchJson<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetchRoute(path, {
    ...init,
    headers: buildHeaders(token, init?.body && !(init.body instanceof FormData) ? "application/json" : undefined),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Setup request failed for ${path}: ${response.status}${detail ? ` ${detail}` : ""}`);
  }

  const payload = await readJson<T>(response);
  if (payload === undefined) {
    throw new Error(`Setup request for ${path} did not return JSON.`);
  }

  return payload;
}

function buildCreateTitleBody(slug: string): JsonRecord {
  return {
    slug,
    contentKind: "game",
    lifecycleStatus: "testing",
    visibility: "private",
    metadata: {
      displayName: "Smoke Test Title",
      shortDescription: "A deterministic contract-smoke title.",
      description: "This title exists so the contract smoke suite can exercise mutable developer routes.",
      genreSlugs: ["utility", "qa"],
      minPlayers: 1,
      maxPlayers: 2,
      ageRatingAuthority: "ESRB",
      ageRatingValue: "E",
      minAgeYears: 6,
    },
  };
}

function buildUpdateTitleBody(slug: string): JsonRecord {
  return {
    slug,
    contentKind: "game",
    lifecycleStatus: "testing",
    visibility: "private",
  };
}

function buildMetadataBody(displayName: string): JsonRecord {
  return {
    displayName,
    shortDescription: "Updated smoke metadata revision.",
    description: "Updated metadata for the smoke test title.",
    genreSlugs: ["utility", "qa"],
    minPlayers: 1,
    maxPlayers: 4,
    ageRatingAuthority: "ESRB",
    ageRatingValue: "E10+",
    minAgeYears: 10,
  };
}

async function bootstrapContext(): Promise<SmokeContext> {
  const developerAuth = requireValue(getRouteToken("developer"), "developer token");
  const playerAuth = getRouteToken("player") || developerAuth;

  const catalog = await fetchJson<{ titles: Array<{ id: string }> }>(
    "/catalog?pageNumber=1&pageSize=5",
    "",
  );
  const publicTitleId = catalog.titles[0]?.id;

  const studios = await fetchJson<{ studios: Array<{ id: string; slug: string }> }>(
    "/developer/studios",
    developerAuth,
  );
  const managedStudio =
    studios.studios.find((studio) => studio.slug === "blue-harbor-games") ?? studios.studios[0];

  const titleList = await fetchJson<{
    titles: Array<{ id: string; slug: string; currentMetadataRevision: number }>;
  }>(`/developer/studios/${managedStudio.id}/titles`, developerAuth);
  const managedTitle =
    titleList.titles.find((title) => title.slug === "compass-echo") ?? titleList.titles[0];

  await fetchJson<{ boardProfile: { boardUserId: string } }>(
    "/identity/me/board-profile",
    playerAuth,
    {
      method: "PUT",
      body: JSON.stringify({
        boardUserId: "board_smoke_player",
        displayName: "Smoke Player",
        avatarUrl: "https://example.invalid/board-smoke-player.png",
      }),
    },
  );

  return {
    publicTitleId: requireValue(publicTitleId, "public title id"),
    managedStudioId: requireValue(managedStudio?.id, "managed studio id"),
    managedStudioSlug: requireValue(managedStudio?.slug, "managed studio slug"),
    managedStudioDisplayName: String((managedStudio as JsonRecord | undefined)?.displayName ?? ""),
    managedStudioDescription: ((managedStudio as JsonRecord | undefined)?.description as string | null | undefined) ?? null,
    managedTitleId: requireValue(managedTitle?.id, "managed title id"),
    managedTitleMetadataRevision: requireNumber(managedTitle?.currentMetadataRevision, "managed title metadata revision"),
    currentUserNotificationId: "",
    createdStudioId: "",
    createdStudioSlug: "",
    createdTitleId: "",
    createdTitleSlug: "",
    createdTitleMetadataRevision: 0,
    createdStudioLinkId: "",
    createdPlayerReportId: "",
    developerReportId: "",
    moderatedDeveloperSubject: "",
    moderatedValidateReportId: "",
    moderatedInvalidateReportId: "",
    releaseUnderTestId: "",
  };
}

function buildRequestPlan(
  route: (typeof maintainedApiRoutes)[number],
  context: SmokeContext,
  token: string,
): RequestPlan {
  const uniqueSuffix = Date.now().toString(36);

  switch (`${route.method} ${route.path}`) {
    case "GET /catalog":
      return {
        path:
          "/catalog?pageNumber=1&pageSize=2&studioSlug=blue-harbor-games&genre=Adventure&contentKind=game&search=lantern&minPlayers=1&maxPlayers=4&sort=title-asc",
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /identity/user-name-availability":
      return {
        path: "/identity/user-name-availability?userName=smoke-user-check",
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /moderation/developers":
      return { path: "/moderation/developers?search=emma", init: { method: route.method, headers: buildHeaders(token) } };
    case "PUT /identity/me/profile":
      return {
        path: "/identity/me/profile",
        init: { method: route.method, headers: buildHeaders(token, "application/json"), body: JSON.stringify({ displayName: "Emma Torres" }) },
      };
    case "POST /studios": {
      const slug = `studio-smoke-${uniqueSuffix}`;
      context.createdStudioSlug = slug;
      return {
        path: "/studios",
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            slug,
            displayName: "Studio Smoke",
            description: "A temporary studio for contract-smoke coverage.",
          }),
        },
      };
    }
    case "GET /identity/me/board-profile":
      return { path: "/identity/me/board-profile", init: { method: route.method, headers: buildHeaders(token) } };
    case "PUT /identity/me/board-profile":
      return {
        path: "/identity/me/board-profile",
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            boardUserId: `board-${uniqueSuffix}`,
            displayName: "Emma on Board",
            avatarUrl: "https://example.invalid/board-profile.png",
          }),
        },
      };
    case "DELETE /identity/me/board-profile":
      return { path: "/identity/me/board-profile", init: { method: route.method, headers: buildHeaders(token) } };
    case "POST /identity/me/notifications/{notificationId}/read":
      return {
        path: `/identity/me/notifications/${requireValue(context.currentUserNotificationId, "current user notification id")}/read`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "PUT /player/library/titles/{titleId}":
    case "DELETE /player/library/titles/{titleId}":
      return {
        path: `/player/library/titles/${requireValue(context.publicTitleId, "public title id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "PUT /player/wishlist/titles/{titleId}":
    case "DELETE /player/wishlist/titles/{titleId}":
      return {
        path: `/player/wishlist/titles/${requireValue(context.publicTitleId, "public title id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /player/reports":
      return {
        path: "/player/reports",
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            titleId: requireValue(context.managedTitleId, "managed title id"),
            reason: "Smoke test report for player flow parity.",
          }),
        },
      };
    case "GET /player/reports/{reportId}":
      return {
        path: `/player/reports/${requireValue(context.createdPlayerReportId, "created player report id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /player/reports/{reportId}/messages":
      return {
        path: `/player/reports/${requireValue(context.createdPlayerReportId, "created player report id")}/messages`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({ message: "Smoke test follow-up from the player workflow." }),
        },
      };
    case "PUT /developer/studios/{studioId}":
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            slug: requireValue(context.createdStudioSlug || context.managedStudioSlug, "studio slug"),
            displayName: "Studio Smoke",
            description: "Updated temporary studio for contract-smoke coverage.",
          }),
        },
      };
    case "DELETE /developer/studios/{studioId}": {
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId, "created studio id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    }
    case "GET /developer/studios/{studioId}/links":
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/links`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /developer/studios/{studioId}/links":
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/links`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            label: "Smoke Docs",
            url: "https://example.invalid/smoke-docs",
          }),
        },
      };
    case "PUT /developer/studios/{studioId}/links/{linkId}":
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/links/${requireValue(context.createdStudioLinkId, "created studio link id")}`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            label: "Smoke Support",
            url: "https://example.invalid/smoke-support",
          }),
        },
      };
    case "DELETE /developer/studios/{studioId}/links/{linkId}":
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/links/${requireValue(context.createdStudioLinkId, "created studio link id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /developer/studios/{studioId}/logo-upload":
    case "POST /developer/studios/{studioId}/avatar-upload":
    case "POST /developer/studios/{studioId}/banner-upload": {
      const formData = new FormData();
      formData.set("media", new Blob([pngPixel], { type: "image/png" }), "smoke.png");
      const uploadPath =
        route.path === "/developer/studios/{studioId}/logo-upload"
          ? "logo-upload"
          : route.path === "/developer/studios/{studioId}/avatar-upload"
            ? "avatar-upload"
            : "banner-upload";
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/${uploadPath}`,
        init: { method: route.method, headers: buildHeaders(token), body: formData },
      };
    }
    case "GET /developer/studios/{studioId}/titles":
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/titles`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /developer/studios/{studioId}/titles": {
      const slug = `smoke-${uniqueSuffix}`;
      context.createdTitleSlug = slug;
      return {
        path: `/developer/studios/${requireValue(context.createdStudioId || context.managedStudioId, "studio id")}/titles`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify(buildCreateTitleBody(slug)),
        },
      };
    }
    case "GET /developer/titles/{titleId}":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "PUT /developer/titles/{titleId}":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify(buildUpdateTitleBody(requireValue(context.createdTitleSlug, "created title slug"))),
        },
      };
    case "PUT /developer/titles/{titleId}/metadata/current":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/metadata/current`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify(buildMetadataBody("Smoke Test Title Revised")),
        },
      };
    case "GET /developer/titles/{titleId}/metadata-versions":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/metadata-versions`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /developer/titles/{titleId}/metadata-versions/{revisionNumber}/activate":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/metadata-versions/${requireNumber(context.createdTitleMetadataRevision, "created title metadata revision")}/activate`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /developer/titles/{titleId}/media":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/media`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "PUT /developer/titles/{titleId}/media/{mediaRole}":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/media/card`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            sourceUrl: "https://example.invalid/smoke-card.png",
            altText: "Smoke card art",
            mimeType: "image/png",
            width: 900,
            height: 1280,
          }),
        },
      };
    case "POST /developer/titles/{titleId}/media/{mediaRole}/upload": {
      const formData = new FormData();
      formData.set("media", new Blob(["smoke-image"], { type: "image/png" }), "smoke.png");
      formData.set("altText", "Uploaded smoke art");
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/media/hero/upload`,
        init: { method: route.method, headers: buildHeaders(token), body: formData },
      };
    }
    case "DELETE /developer/titles/{titleId}/media/{mediaRole}":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/media/hero`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /developer/titles/{titleId}/reports":
      return {
        path: `/developer/titles/${requireValue(context.managedTitleId, "managed title id")}/reports`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /developer/titles/{titleId}/reports/{reportId}":
      return {
        path: `/developer/titles/${requireValue(context.managedTitleId, "managed title id")}/reports/${requireValue(context.developerReportId, "developer report id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /developer/titles/{titleId}/reports/{reportId}/messages":
      return {
        path: `/developer/titles/${requireValue(context.managedTitleId, "managed title id")}/reports/${requireValue(context.developerReportId, "developer report id")}/messages`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({ message: "Smoke test response from the developer workflow." }),
        },
      };
    case "GET /developer/titles/{titleId}/releases":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/releases`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /developer/titles/{titleId}/releases":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/releases`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            version: "0.1.0-smoke",
            status: "testing",
            acquisitionUrl: "https://boardenthusiasts.example/releases/0.1.0-smoke",
          }),
        },
      };
    case "PUT /developer/titles/{titleId}/releases/{releaseId}":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/releases/${requireValue(context.releaseUnderTestId, "release under test id")}`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({
            version: "0.1.1-smoke",
            status: "production",
            acquisitionUrl: "https://boardenthusiasts.example/releases/0.1.1-smoke",
          }),
        },
      };
    case "POST /developer/titles/{titleId}/releases/{releaseId}/activate":
      return {
        path: `/developer/titles/${requireValue(context.createdTitleId, "created title id")}/releases/${requireValue(context.releaseUnderTestId, "release under test id")}/activate`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /moderation/developers/{developerSubject}/verification":
      return {
        path: `/moderation/developers/${requireValue(context.moderatedDeveloperSubject, "moderated developer subject")}/verification`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "PUT /moderation/developers/{developerSubject}/verified-developer":
      return {
        path: `/moderation/developers/${requireValue(context.moderatedDeveloperSubject, "moderated developer subject")}/verified-developer`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "DELETE /moderation/developers/{developerSubject}/verified-developer":
      return {
        path: `/moderation/developers/${requireValue(context.moderatedDeveloperSubject, "moderated developer subject")}/verified-developer`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "GET /moderation/title-reports/{reportId}":
      return {
        path: `/moderation/title-reports/${requireValue(context.moderatedValidateReportId, "moderation validate report id")}`,
        init: { method: route.method, headers: buildHeaders(token) },
      };
    case "POST /moderation/title-reports/{reportId}/messages":
      return {
        path: `/moderation/title-reports/${requireValue(context.moderatedValidateReportId, "moderation validate report id")}/messages`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({ message: "Smoke test moderation follow-up.", recipientRole: "developer" }),
        },
      };
    case "POST /moderation/title-reports/{reportId}/validate":
      return {
        path: `/moderation/title-reports/${requireValue(context.moderatedValidateReportId, "moderation validate report id")}/validate`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({ note: "Validated by contract smoke." }),
        },
      };
    case "POST /moderation/title-reports/{reportId}/invalidate":
      return {
        path: `/moderation/title-reports/${requireValue(context.moderatedInvalidateReportId || context.moderatedValidateReportId, "moderation invalidate report id")}/invalidate`,
        init: {
          method: route.method,
          headers: buildHeaders(token, "application/json"),
          body: JSON.stringify({ note: "Invalidated by contract smoke." }),
        },
      };
    default:
      return { path: route.path, init: { method: route.method, headers: buildHeaders(token) } };
  }
}

function applyResponseContext(route: (typeof maintainedApiRoutes)[number], payload: unknown, context: SmokeContext): void {
  if (!payload || typeof payload !== "object") {
    return;
  }

  const json = payload as JsonRecord;

  switch (`${route.method} ${route.path}`) {
    case "POST /player/reports":
      context.createdPlayerReportId = (((json.report as JsonRecord | undefined)?.id as string | undefined) ?? "");
      break;
    case "GET /identity/me/notifications": {
      const notifications = (json.notifications as Array<JsonRecord> | undefined) ?? [];
      context.currentUserNotificationId = ((notifications[0]?.id as string | undefined) ?? "");
      break;
    }
    case "POST /studios":
      context.createdStudioId = (((json.studio as JsonRecord | undefined)?.id as string | undefined) ?? "");
      break;
    case "POST /developer/studios/{studioId}/links":
      context.createdStudioLinkId = (((json.link as JsonRecord | undefined)?.id as string | undefined) ?? "");
      break;
    case "POST /developer/studios/{studioId}/titles":
      context.createdTitleId = (((json.title as JsonRecord | undefined)?.id as string | undefined) ?? "");
      context.createdTitleMetadataRevision = Number(((json.title as JsonRecord | undefined)?.currentMetadataRevision as number | undefined) ?? 0);
      break;
    case "GET /developer/titles/{titleId}":
    case "PUT /developer/titles/{titleId}":
    case "PUT /developer/titles/{titleId}/metadata/current":
    case "POST /developer/titles/{titleId}/metadata-versions/{revisionNumber}/activate":
      context.createdTitleMetadataRevision = Number(((json.title as JsonRecord | undefined)?.currentMetadataRevision as number | undefined) ?? context.createdTitleMetadataRevision);
      break;
    case "GET /developer/titles/{titleId}/reports": {
      const reports = (json.reports as Array<JsonRecord> | undefined) ?? [];
      context.developerReportId = ((reports[0]?.id as string | undefined) ?? "");
      break;
    }
    case "GET /moderation/developers": {
      const developers = (json.developers as Array<JsonRecord> | undefined) ?? [];
      context.moderatedDeveloperSubject = ((developers[0]?.developerSubject as string | undefined) ?? "");
      break;
    }
    case "POST /developer/titles/{titleId}/releases":
      context.releaseUnderTestId = (((json.release as JsonRecord | undefined)?.id as string | undefined) ?? "");
      break;
    case "GET /moderation/title-reports": {
      const reports = (json.reports as Array<JsonRecord> | undefined) ?? [];
      context.moderatedValidateReportId = ((reports[0]?.id as string | undefined) ?? "");
      context.moderatedInvalidateReportId = ((reports[1]?.id as string | undefined) ?? context.moderatedValidateReportId);
      break;
    }
    default:
      break;
  }
}

async function run(): Promise<void> {
  const results: SmokeResult[] = [];
  const context = await bootstrapContext();

  for (const route of maintainedApiRoutes) {
    const routeToken = getRouteToken(route.access);

    if (!routeToken && route.authMode !== "public") {
      results.push({
        route: `${route.method} ${route.path}`,
        status: 401,
        ok: true,
        detail: route.description,
      });
      continue;
    }

    const plan = buildRequestPlan(route, context, routeToken);
    const response = await fetchRoute(plan.path, plan.init);
    const payload = await readJson<unknown>(response);
    const ok = response.ok;

    if (ok) {
      applyResponseContext(route, payload, context);
    }

    results.push({
      route: `${route.method} ${plan.path}`,
      status: response.status,
      ok,
      detail: route.description,
    });
  }

  const failures = results.filter((result) => !result.ok);
  for (const result of results) {
    console.log(`${result.ok ? "PASS" : "FAIL"} ${result.route} -> ${result.status} (${result.detail})`);
  }

  if (failures.length > 0) {
    throw new Error(`Contract smoke failed for ${failures.length} route(s).`);
  }
}

run().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exitCode = 1;
});
