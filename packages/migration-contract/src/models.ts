export interface MigrationEnvironmentLayout {
  appName: string;
  frontendBaseUrl: string;
  apiBaseUrl: string;
  supabaseProjectRef: string;
  supabaseUrl: string;
  supabaseAnonKeyVariable: string;
  supabaseServiceRoleKeyVariable: string;
}

export const localMigrationEnvironment: MigrationEnvironmentLayout = {
  appName: "board-enthusiasts-local",
  frontendBaseUrl: "http://127.0.0.1:4173",
  apiBaseUrl: "http://127.0.0.1:8787",
  supabaseProjectRef: "local-dev",
  supabaseUrl: "http://127.0.0.1:54321",
  supabaseAnonKeyVariable: "SUPABASE_ANON_KEY",
  supabaseServiceRoleKeyVariable: "SUPABASE_SERVICE_ROLE_KEY"
};

export const stagingMigrationEnvironment: MigrationEnvironmentLayout = {
  appName: "board-enthusiasts-staging",
  frontendBaseUrl: "https://staging.boardenthusiasts.com",
  apiBaseUrl: "https://api.staging.boardenthusiasts.com",
  supabaseProjectRef: "staging-project-ref",
  supabaseUrl: "https://<project-ref>.supabase.co",
  supabaseAnonKeyVariable: "SUPABASE_ANON_KEY",
  supabaseServiceRoleKeyVariable: "SUPABASE_SERVICE_ROLE_KEY"
};
