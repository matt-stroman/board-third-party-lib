import { maintainedApiRoutes } from "../../packages/migration-contract/src/index";

const baseUrl = (process.env.CONTRACT_SMOKE_BASE_URL ?? "https://localhost:7085").replace(/\/$/, "");
const fallbackToken = (process.env.CONTRACT_SMOKE_TOKEN ?? "").trim();
const playerToken = (process.env.CONTRACT_SMOKE_PLAYER_TOKEN ?? "").trim();
const developerToken = (process.env.CONTRACT_SMOKE_DEVELOPER_TOKEN ?? "").trim();
const moderatorToken = (process.env.CONTRACT_SMOKE_MODERATOR_TOKEN ?? "").trim();

interface SmokeResult {
  route: string;
  status: number;
  ok: boolean;
  detail: string;
}

async function fetchRoute(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${baseUrl}${path}`, init);
}

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

function buildHeaders(token: string): HeadersInit {
  if (!token) {
    return {};
  }

  return {
    Authorization: `Bearer ${token}`
  };
}

async function run(): Promise<void> {
  const results: SmokeResult[] = [];

  for (const route of maintainedApiRoutes) {
    const path =
      route.path === "/catalog"
        ? "/catalog?pageNumber=1&pageSize=2"
        : route.path === "/moderation/developers"
          ? "/moderation/developers?search=emma"
          : route.path === "/identity/me/profile" && route.method === "PUT"
            ? "/identity/me/profile"
          : route.path;

    const body =
      route.path === "/identity/me/profile" && route.method === "PUT"
        ? JSON.stringify({ displayName: "Emma Torres" })
        : undefined;
    const routeToken = getRouteToken(route.access);

    const response = await fetchRoute(path, {
      method: route.method,
      headers: {
        ...buildHeaders(routeToken),
        ...(body ? { "content-type": "application/json" } : {})
      },
      body
    });

    const ok =
      route.authMode === "public"
        ? response.ok
        : routeToken
          ? response.ok
          : response.status === 401;

    results.push({
      route: `${route.method} ${path}`,
      status: response.status,
      ok,
      detail: route.description
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
