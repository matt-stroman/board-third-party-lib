import { getMaintainedSurface } from "./service-boundary";

function json(data: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(data, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8"
    },
    ...init
  });
}

export interface Env {
  APP_ENV?: string;
  SUPABASE_URL?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const envName = env.APP_ENV ?? "local";

    if (url.pathname === "/") {
      return json({
        service: "board-enthusiasts-workers-api",
        phase: "wave-1-shell",
        environment: envName
      });
    }

    if (url.pathname === "/health/live") {
      return json({ status: "healthy", environment: envName });
    }

    if (url.pathname === "/health/ready") {
      return json({
        status: "ready",
        environment: envName,
        supabaseUrlConfigured: Boolean(env.SUPABASE_URL)
      });
    }

    if (url.pathname === "/_migration/surface") {
      return json(getMaintainedSurface({ envName }));
    }

    return json(
      {
        error: "not_implemented",
        message: "Wave 1 only scaffolds the Workers runtime shell. Maintained API parity begins in Wave 2."
      },
      { status: 501 }
    );
  }
};
