export type MaintainedAccessLevel = "public" | "player" | "developer" | "moderator";

export interface MaintainedUiRoute {
  path: string;
  label: string;
  access: MaintainedAccessLevel;
  parityMarker: string;
}

export const maintainedUiRoutes: ReadonlyArray<MaintainedUiRoute> = [
  { path: "/", label: "Home", access: "public", parityMarker: "Board Enthusiasts" },
  { path: "/browse", label: "Browse", access: "public", parityMarker: "Browse" },
  { path: "/studios/blue-harbor-games", label: "Public Studio", access: "public", parityMarker: "Blue Harbor Games" },
  { path: "/browse/blue-harbor-games/lantern-drift", label: "Public Title", access: "public", parityMarker: "Lantern Drift" },
  { path: "/player", label: "Player Workspace", access: "player", parityMarker: "My Games" },
  { path: "/develop", label: "Developer Workspace", access: "developer", parityMarker: "Developer Console" },
  { path: "/moderate", label: "Moderation Workspace", access: "moderator", parityMarker: "Verify Developers" }
];

export interface MaintainedApiRoute {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  description: string;
  access: MaintainedAccessLevel;
  authMode: "public" | "token-optional" | "token-required";
}

export const maintainedApiRoutes: ReadonlyArray<MaintainedApiRoute> = [
  { method: "GET", path: "/health/live", description: "Live health probe", access: "public", authMode: "public" },
  { method: "GET", path: "/health/ready", description: "Ready health probe", access: "public", authMode: "public" },
  { method: "GET", path: "/catalog", description: "Public catalog listing", access: "public", authMode: "public" },
  { method: "GET", path: "/studios", description: "Public studio listing", access: "public", authMode: "public" },
  { method: "GET", path: "/catalog/blue-harbor-games/lantern-drift", description: "Public catalog detail", access: "public", authMode: "public" },
  { method: "GET", path: "/studios/blue-harbor-games", description: "Public studio detail", access: "public", authMode: "public" },
  { method: "GET", path: "/identity/me", description: "Current-user bootstrap", access: "player", authMode: "token-required" },
  { method: "GET", path: "/identity/me/profile", description: "Current-user profile read", access: "player", authMode: "token-required" },
  { method: "PUT", path: "/identity/me/profile", description: "Current-user profile update", access: "player", authMode: "token-required" },
  { method: "GET", path: "/identity/me/developer-enrollment", description: "Developer access read model", access: "player", authMode: "token-required" },
  { method: "POST", path: "/identity/me/developer-enrollment", description: "Developer self-enrollment", access: "player", authMode: "token-required" },
  { method: "GET", path: "/developer/studios", description: "Developer studio workspace list", access: "developer", authMode: "token-required" },
  { method: "GET", path: "/moderation/developers", description: "Moderation developer search", access: "moderator", authMode: "token-required" }
];
