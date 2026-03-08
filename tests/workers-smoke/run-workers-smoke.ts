const baseUrl = (process.env.WORKERS_SMOKE_BASE_URL ?? "http://127.0.0.1:8787").replace(/\/$/, "");
const moderatorToken = (process.env.WORKERS_SMOKE_MODERATOR_TOKEN ?? "").trim();
const developerToken = (process.env.WORKERS_SMOKE_DEVELOPER_TOKEN ?? "").trim();

if (!moderatorToken || !developerToken) {
  throw new Error("WORKERS_SMOKE_MODERATOR_TOKEN and WORKERS_SMOKE_DEVELOPER_TOKEN are required.");
}

interface SmokeResult {
  ok: boolean;
  label: string;
  detail: string;
}

const pngPixel = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9pX6N6gAAAAASUVORK5CYII="),
  (character) => character.charCodeAt(0)
);

async function fetchJson(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${baseUrl}${path}`, init);
}

async function assertJson(path: string, init: RequestInit, expectedStatus: number, label: string): Promise<unknown> {
  const response = await fetchJson(path, init);
  if (response.status !== expectedStatus) {
    const text = await response.text();
    throw new Error(`${label} expected ${expectedStatus} but received ${response.status}.\n${text}`);
  }

  if (expectedStatus === 204) {
    return null;
  }

  return response.json();
}

function authHeaders(token: string, contentType = "application/json"): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    ...(contentType ? { "content-type": contentType } : {})
  };
}

async function run(): Promise<void> {
  const results: SmokeResult[] = [];

  const catalog = (await assertJson("/catalog?pageNumber=1&pageSize=2", {}, 200, "catalog list")) as {
    titles: Array<{ slug: string }>;
  };
  results.push({ ok: catalog.titles.length >= 2, label: "catalog list", detail: "public titles returned" });

  const title = (await assertJson("/catalog/blue-harbor-games/lantern-drift", {}, 200, "catalog detail")) as {
    title: { mediaAssets: Array<{ sourceUrl: string }> };
  };
  results.push({ ok: title.title.mediaAssets.length >= 1, label: "catalog detail", detail: "public title detail returned" });

  await assertJson("/identity/me", { headers: authHeaders(developerToken, "") }, 200, "identity bootstrap");
  await assertJson("/identity/me/profile", { headers: authHeaders(developerToken, "") }, 200, "profile read");
  await assertJson(
    "/identity/me/profile",
    {
      method: "PUT",
      headers: authHeaders(developerToken),
      body: JSON.stringify({ displayName: "Emma Torres" })
    },
    200,
    "profile update"
  );
  await assertJson("/identity/me/developer-enrollment", { headers: authHeaders(developerToken, "") }, 200, "developer enrollment read");
  await assertJson(
    "/identity/me/developer-enrollment",
    { method: "POST", headers: authHeaders(developerToken, "") },
    200,
    "developer enrollment write"
  );
  results.push({ ok: true, label: "identity flows", detail: "bootstrap, profile, and developer enrollment succeeded" });

  const managedStudios = (await assertJson("/developer/studios", { headers: authHeaders(developerToken, "") }, 200, "managed studios")) as {
    studios: Array<{ id: string; slug: string }>;
  };
  const blueHarbor = managedStudios.studios.find((studio) => studio.slug === "blue-harbor-games");
  if (!blueHarbor) {
    throw new Error("Developer managed studios response did not include blue-harbor-games.");
  }

  const createdStudio = (await assertJson(
    "/studios",
    {
      method: "POST",
      headers: authHeaders(developerToken),
      body: JSON.stringify({
        slug: "ember-cove-lab",
        displayName: "Ember Cove Lab",
        description: "Temporary Wave 2 smoke studio."
      })
    },
    201,
    "studio create"
  )) as { studio: { id: string } };

  const createdLink = (await assertJson(
    `/developer/studios/${blueHarbor.id}/links`,
    {
      method: "POST",
      headers: authHeaders(developerToken),
      body: JSON.stringify({
        label: "Docs",
        url: "https://blueharborgames.example/docs"
      })
    },
    201,
    "studio link create"
  )) as { link: { id: string } };

  await assertJson(
    `/developer/studios/${blueHarbor.id}/links/${createdLink.link.id}`,
    {
      method: "PUT",
      headers: authHeaders(developerToken),
      body: JSON.stringify({
        label: "Support",
        url: "https://blueharborgames.example/support"
      })
    },
    200,
    "studio link update"
  );
  await assertJson(
    `/developer/studios/${blueHarbor.id}/links/${createdLink.link.id}`,
    {
      method: "DELETE",
      headers: authHeaders(developerToken, "")
    },
    204,
    "studio link delete"
  );

  const uploadFile = new File([pngPixel], "logo.png", { type: "image/png" });
  const uploadForm = new FormData();
  uploadForm.set("media", uploadFile);
  const uploadedLogo = (await assertJson(
    `/developer/studios/${blueHarbor.id}/logo-upload`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${developerToken}`
      },
      body: uploadForm
    },
    200,
    "studio logo upload"
  )) as { studio: { logoUrl: string | null } };
  if (!uploadedLogo.studio.logoUrl) {
    throw new Error("Studio logo upload did not return a logoUrl.");
  }
  const uploadedLogoResponse = await fetch(uploadedLogo.studio.logoUrl);
  if (!uploadedLogoResponse.ok) {
    throw new Error(`Uploaded studio logo was not retrievable: ${uploadedLogoResponse.status}`);
  }

  await assertJson(
    `/developer/studios/${createdStudio.studio.id}`,
    {
      method: "DELETE",
      headers: authHeaders(developerToken, "")
    },
    204,
    "studio delete"
  );
  results.push({ ok: true, label: "developer studio flows", detail: "studio create/delete, links, and media upload succeeded" });

  const moderationSearch = (await assertJson(
    "/moderation/developers?search=olivia",
    {
      headers: authHeaders(moderatorToken, "")
    },
    200,
    "moderation search"
  )) as { developers: Array<{ developerSubject: string; userName: string | null }> };
  const olivia = moderationSearch.developers.find((developer) => developer.userName === "olivia.bennett");
  if (!olivia) {
    throw new Error("Moderation developer search did not return olivia.bennett.");
  }

  await assertJson(
    `/moderation/developers/${olivia.developerSubject}/verification`,
    { headers: authHeaders(moderatorToken, "") },
    200,
    "moderation verification read"
  );
  await assertJson(
    `/moderation/developers/${olivia.developerSubject}/verified-developer`,
    { method: "PUT", headers: authHeaders(moderatorToken, "") },
    200,
    "moderation verification grant"
  );
  await assertJson(
    `/moderation/developers/${olivia.developerSubject}/verified-developer`,
    { method: "DELETE", headers: authHeaders(moderatorToken, "") },
    200,
    "moderation verification revoke"
  );
  results.push({ ok: true, label: "moderation flows", detail: "search and verification mutation succeeded" });

  for (const result of results) {
    console.log(`PASS ${result.label} (${result.detail})`);
  }
}

run().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exitCode = 1;
});
