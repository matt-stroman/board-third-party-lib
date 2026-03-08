import { maintainedApiRoutes } from "@board-enthusiasts/migration-contract";

export interface WorkerAppContext {
  envName: string;
}

export interface MaintainedSurfaceResponse {
  environment: string;
  maintainedApiRoutes: typeof maintainedApiRoutes;
}

export function getMaintainedSurface(context: WorkerAppContext): MaintainedSurfaceResponse {
  return {
    environment: context.envName,
    maintainedApiRoutes
  };
}
