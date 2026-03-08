import { maintainedUiRoutes, type MaintainedUiRoute } from "@board-enthusiasts/migration-contract";
import { Link, Route, Routes, useLocation } from "react-router-dom";

function findRoute(pathname: string): MaintainedUiRoute | undefined {
  if (pathname.startsWith("/studios/")) {
    return maintainedUiRoutes.find((route) => route.path === "/studios/blue-harbor-games");
  }

  if (pathname.startsWith("/browse/")) {
    return maintainedUiRoutes.find((route) => route.path === "/browse/blue-harbor-games/lantern-drift");
  }

  return maintainedUiRoutes.find((route) => route.path === pathname);
}

function PlaceholderPage({ route }: { route: MaintainedUiRoute }) {
  return (
    <section className="panel">
      <div className="eyebrow">{route.access.toUpperCase()} parity target</div>
      <h1>{route.label}</h1>
      <p>
        Wave 1 establishes route parity, shell structure, and tooling only. This page is the React placeholder for{" "}
        <code>{route.path}</code>.
      </p>
      <p className="marker">Parity marker: {route.parityMarker}</p>
    </section>
  );
}

function NotFoundPage() {
  return (
    <section className="panel">
      <div className="eyebrow">Migration shell</div>
      <h1>Route reserved for parity porting</h1>
      <p>The requested route has not been scaffolded yet in the SPA shell.</p>
    </section>
  );
}

function Shell() {
  const location = useLocation();
  const activeRoute = findRoute(location.pathname);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="brand">Board Enthusiasts</div>
          <div className="subhead">Cloudflare Pages React shell for UX parity work</div>
        </div>
        <nav className="nav">
          {maintainedUiRoutes.map((route) => (
            <Link key={route.path} to={route.path}>
              {route.label}
            </Link>
          ))}
        </nav>
      </header>

      <main className="main-grid">
        <aside className="panel sidebar">
          <div className="eyebrow">Wave 1 scope</div>
          <h2>Migration target locked</h2>
          <ul>
            <li>React SPA route inventory matches maintained UX paths.</li>
            <li>Shared route metadata lives in the TypeScript contract package.</li>
            <li>Current route focus: {activeRoute?.label ?? "Unmapped route"}.</li>
          </ul>
        </aside>

        <Routes>
          {maintainedUiRoutes.map((route) => (
            <Route key={route.path} path={route.path} element={<PlaceholderPage route={route} />} />
          ))}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return <Shell />;
}
