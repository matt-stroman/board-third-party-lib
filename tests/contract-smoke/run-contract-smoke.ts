import { maintainedApiRoutes } from "../../packages/migration-contract/src/index";

const baseUrl = (process.env.CONTRACT_SMOKE_BASE_URL ?? "https://localhost:7085").replace(/\/$/, "");
const bearerToken = (process.env.CONTRACT_SMOKE_TOKEN ?? "").trim();

interface SmokeResult {
  route: string;
  status: number;
  ok: boolean;
  detail: string;
}

async function fetchRoute(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${baseUrl}${path}`, init);
}

function buildHeaders(): HeadersInit {
  if (!bearerToken) {
    return {};
  }

  return {
    Authorization: `Bearer ${bearerToken}`
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
          : route.path;

    const response = await fetchRoute(path, {
      method: route.method,
      headers: buildHeaders()
    });

    const ok =
      route.authMode === "public"
        ? response.ok
        : bearerToken
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
