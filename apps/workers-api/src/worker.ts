import { empty, json, ApiError, validationProblem } from "./http";
import { Env, getMaintainedSurface, WorkerAppService } from "./service-boundary";

function getBearerToken(request: Request): string {
  const header = request.headers.get("authorization") ?? request.headers.get("Authorization") ?? "";
  return header.startsWith("Bearer ") ? header.slice("Bearer ".length).trim() : "";
}

async function readJson<T>(request: Request): Promise<T> {
  try {
    return (await request.json()) as T;
  } catch {
    throw validationProblem({
      body: ["Request body must be valid JSON."]
    });
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const service = new WorkerAppService(env);
    const url = new URL(request.url);
    const token = getBearerToken(request);

    try {
      if (url.pathname === "/") {
        return json({
          service: "board-enthusiasts-workers-api",
          phase: "wave-2-platform-api",
          environment: service.getContext().envName
        });
      }

      if (url.pathname === "/health/live") {
        return json({ status: "healthy", environment: service.getContext().envName });
      }

      if (url.pathname === "/health/ready") {
        return json(await service.getReadyState());
      }

      if (url.pathname === "/_migration/surface") {
        return json(getMaintainedSurface(service.getContext()));
      }

      if (request.method === "GET" && url.pathname === "/catalog") {
        const pageNumber = url.searchParams.get("pageNumber");
        const pageSize = url.searchParams.get("pageSize");
        return json(
          await service.listCatalogTitles({
            studioSlug: url.searchParams.get("studioSlug") ?? undefined,
            contentKind: (url.searchParams.get("contentKind") as "game" | "app" | null) ?? undefined,
            genre: url.searchParams.get("genre") ?? undefined,
            sort: (url.searchParams.get("sort") as "title" | "genre" | null) ?? undefined,
            pageNumber: pageNumber ? Number(pageNumber) : undefined,
            pageSize: pageSize ? Number(pageSize) : undefined
          })
        );
      }

      const catalogMatch = url.pathname.match(/^\/catalog\/([^/]+)\/([^/]+)$/);
      if (request.method === "GET" && catalogMatch) {
        return json(await service.getCatalogTitle(catalogMatch[1]!, catalogMatch[2]!));
      }

      if (request.method === "GET" && url.pathname === "/studios") {
        return json(await service.listPublicStudios());
      }

      const studioSlugMatch = url.pathname.match(/^\/studios\/([^/]+)$/);
      if (request.method === "GET" && studioSlugMatch) {
        return json(await service.getPublicStudio(studioSlugMatch[1]!));
      }

      if (request.method === "GET" && url.pathname === "/identity/me") {
        return json(await service.getCurrentUserResponse(token));
      }

      if (request.method === "GET" && url.pathname === "/identity/me/profile") {
        return json(await service.getCurrentUserProfile(token));
      }

      if (request.method === "PUT" && url.pathname === "/identity/me/profile") {
        const body = await readJson<{ displayName?: string | null }>(request);
        return json(await service.updateCurrentUserProfile(token, body));
      }

      if (request.method === "GET" && url.pathname === "/identity/me/developer-enrollment") {
        return json(await service.getDeveloperEnrollment(token));
      }

      if (request.method === "POST" && url.pathname === "/identity/me/developer-enrollment") {
        return json(await service.enrollCurrentUserAsDeveloper(token));
      }

      if (request.method === "GET" && url.pathname === "/moderation/developers") {
        return json(await service.listModerationDevelopers(token, url.searchParams.get("search")));
      }

      const developerVerificationMatch = url.pathname.match(/^\/moderation\/developers\/([^/]+)\/verification$/);
      if (request.method === "GET" && developerVerificationMatch) {
        return json(await service.getVerifiedDeveloperState(token, developerVerificationMatch[1]!));
      }

      const verifiedDeveloperMatch = url.pathname.match(/^\/moderation\/developers\/([^/]+)\/verified-developer$/);
      if (verifiedDeveloperMatch && request.method === "PUT") {
        return json(await service.setVerifiedDeveloperState(token, verifiedDeveloperMatch[1]!, true));
      }

      if (verifiedDeveloperMatch && request.method === "DELETE") {
        return json(await service.setVerifiedDeveloperState(token, verifiedDeveloperMatch[1]!, false));
      }

      if (request.method === "GET" && url.pathname === "/developer/studios") {
        return json(await service.listManagedStudios(token));
      }

      if (request.method === "POST" && url.pathname === "/studios") {
        return json(await service.createStudio(token, await readJson(request)), { status: 201 });
      }

      const studioIdMatch = url.pathname.match(/^\/developer\/studios\/([^/]+)$/);
      if (studioIdMatch && request.method === "PUT") {
        return json(await service.updateStudio(token, studioIdMatch[1]!, await readJson(request)));
      }

      if (studioIdMatch && request.method === "DELETE") {
        await service.deleteStudio(token, studioIdMatch[1]!);
        return empty();
      }

      const studioLinksMatch = url.pathname.match(/^\/developer\/studios\/([^/]+)\/links$/);
      if (studioLinksMatch && request.method === "GET") {
        return json(await service.listStudioLinks(token, studioLinksMatch[1]!));
      }

      if (studioLinksMatch && request.method === "POST") {
        return json(await service.createStudioLink(token, studioLinksMatch[1]!, await readJson(request)), { status: 201 });
      }

      const studioLinkMatch = url.pathname.match(/^\/developer\/studios\/([^/]+)\/links\/([^/]+)$/);
      if (studioLinkMatch && request.method === "PUT") {
        return json(await service.updateStudioLink(token, studioLinkMatch[1]!, studioLinkMatch[2]!, await readJson(request)));
      }

      if (studioLinkMatch && request.method === "DELETE") {
        await service.deleteStudioLink(token, studioLinkMatch[1]!, studioLinkMatch[2]!);
        return empty();
      }

      const studioLogoMatch = url.pathname.match(/^\/developer\/studios\/([^/]+)\/logo-upload$/);
      if (studioLogoMatch && request.method === "POST") {
        const formData = await request.formData();
        return json(await service.uploadStudioMedia(token, studioLogoMatch[1]!, "logo", formData.get("media") as File | null));
      }

      const studioBannerMatch = url.pathname.match(/^\/developer\/studios\/([^/]+)\/banner-upload$/);
      if (studioBannerMatch && request.method === "POST") {
        const formData = await request.formData();
        return json(await service.uploadStudioMedia(token, studioBannerMatch[1]!, "banner", formData.get("media") as File | null));
      }

      return json(
        {
          error: "not_found",
          message: `No route matched ${request.method} ${url.pathname}`
        },
        { status: 404 }
      );
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        return json(error.payload, { status: error.status });
      }

      const message = error instanceof Error ? error.message : String(error);
      return json(
        {
          type: "https://boardtpl.dev/problems/unhandled-error",
          title: "Unhandled worker error",
          status: 500,
          detail: message,
          code: "unhandled_worker_error"
        },
        { status: 500 }
      );
    }
  }
};
