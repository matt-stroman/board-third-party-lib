const baseUrl = (process.env.WORKERS_SMOKE_BASE_URL ?? "http://127.0.0.1:8787").replace(/\/$/, "");
const playerToken = (process.env.WORKERS_SMOKE_PLAYER_TOKEN ?? "").trim();
const moderatorToken = (process.env.WORKERS_SMOKE_MODERATOR_TOKEN ?? "").trim();
const developerToken = (process.env.WORKERS_SMOKE_DEVELOPER_TOKEN ?? "").trim();

if (!playerToken || !moderatorToken || !developerToken) {
  throw new Error("WORKERS_SMOKE_PLAYER_TOKEN, WORKERS_SMOKE_MODERATOR_TOKEN, and WORKERS_SMOKE_DEVELOPER_TOKEN are required.");
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

  const metadata = (await assertJson("/", {}, 200, "api metadata")) as {
    service: string;
  };
  if (metadata.service !== "board-enthusiasts-workers-api") {
    throw new Error("Root API metadata did not return the expected service name.");
  }

  const genres = (await assertJson("/genres", {}, 200, "genre list")) as { genres: Array<{ slug: string }> };
  const ageRatingAuthorities = (await assertJson("/age-rating-authorities", {}, 200, "age-rating authority list")) as {
    ageRatingAuthorities: Array<{ code: string }>;
  };
  const catalog = (await assertJson(
    "/catalog?pageNumber=1&pageSize=4&sort=title-asc",
    {},
    200,
    "catalog list"
  )) as {
    titles: Array<{ id: string; studioSlug: string; slug: string }>;
  };
  const studios = (await assertJson("/studios", {}, 200, "studio list")) as {
    studios: Array<{ slug: string }>;
  };
  const userNameAvailability = (await assertJson(
    "/identity/user-name-availability?userName=workers-smoke-check",
    {},
    200,
    "username availability"
  )) as {
    userNameAvailability: { normalizedUserName: string };
  };
  await assertJson("/catalog/blue-harbor-games/lantern-drift", {}, 200, "catalog detail");
  await assertJson("/studios/blue-harbor-games", {}, 200, "studio detail");
  results.push({
    ok:
      genres.genres.length > 0 &&
      ageRatingAuthorities.ageRatingAuthorities.length > 0 &&
      catalog.titles.length > 0 &&
      studios.studios.length > 0 &&
      userNameAvailability.userNameAvailability.normalizedUserName === "workers-smoke-check",
    label: "public browse flows",
    detail: "metadata, browse helpers, catalog, studios, and username availability succeeded"
  });

  const publicTitleId = catalog.titles[0]?.id;
  if (!publicTitleId) {
    throw new Error("Public catalog list did not return a title id for player collection checks.");
  }

  await assertJson("/identity/me", { headers: authHeaders(playerToken, "") }, 200, "player identity bootstrap");
  await assertJson("/identity/me/profile", { headers: authHeaders(playerToken, "") }, 200, "player profile read");
  await assertJson(
    "/identity/me/profile",
    {
      method: "PUT",
      headers: authHeaders(playerToken),
      body: JSON.stringify({ displayName: "Ava Garcia" })
    },
    200,
    "player profile update"
  );
  const playerNotifications = (await assertJson(
    "/identity/me/notifications",
    { headers: authHeaders(playerToken, "") },
    200,
    "player notifications"
  )) as {
    notifications: Array<{ id: string }>;
  };
  if (playerNotifications.notifications.length > 0) {
    await assertJson(
      `/identity/me/notifications/${playerNotifications.notifications[0]!.id}/read`,
      { method: "POST", headers: authHeaders(playerToken, "") },
      200,
      "player notification read"
    );
  }
  await assertJson(
    "/identity/me/board-profile",
    {
      method: "PUT",
      headers: authHeaders(playerToken),
      body: JSON.stringify({
        boardUserId: "board_workers_smoke_player",
        displayName: "Workers Smoke Player",
        avatarUrl: "https://example.invalid/board-workers-smoke-player.png"
      })
    },
    200,
    "player board profile upsert"
  );
  await assertJson("/identity/me/board-profile", { headers: authHeaders(playerToken, "") }, 200, "player board profile read");
  await assertJson(
    "/identity/me/board-profile",
    {
      method: "DELETE",
      headers: authHeaders(playerToken, "")
    },
    204,
    "player board profile delete"
  );
  await assertJson("/identity/me/developer-enrollment", { headers: authHeaders(playerToken, "") }, 200, "player developer enrollment read");
  results.push({
    ok: true,
    label: "player identity flows",
    detail: "identity bootstrap, profile, notifications, board profile, and enrollment read succeeded"
  });

  await assertJson("/player/library", { headers: authHeaders(playerToken, "") }, 200, "player library read");
  await assertJson(
    `/player/library/titles/${publicTitleId}`,
    { method: "PUT", headers: authHeaders(playerToken, "") },
    200,
    "player library add"
  );
  await assertJson(
    `/player/library/titles/${publicTitleId}`,
    { method: "DELETE", headers: authHeaders(playerToken, "") },
    200,
    "player library remove"
  );
  await assertJson("/player/wishlist", { headers: authHeaders(playerToken, "") }, 200, "player wishlist read");
  await assertJson(
    `/player/wishlist/titles/${publicTitleId}`,
    { method: "PUT", headers: authHeaders(playerToken, "") },
    200,
    "player wishlist add"
  );
  await assertJson(
    `/player/wishlist/titles/${publicTitleId}`,
    { method: "DELETE", headers: authHeaders(playerToken, "") },
    200,
    "player wishlist remove"
  );
  results.push({
    ok: true,
    label: "player collection flows",
    detail: "library and wishlist CRUD succeeded"
  });

  await assertJson("/identity/me", { headers: authHeaders(developerToken, "") }, 200, "developer identity bootstrap");
  await assertJson("/identity/me/profile", { headers: authHeaders(developerToken, "") }, 200, "developer profile read");
  await assertJson(
    "/identity/me/profile",
    {
      method: "PUT",
      headers: authHeaders(developerToken),
      body: JSON.stringify({ displayName: "Emma Torres" })
    },
    200,
    "developer profile update"
  );
  await assertJson("/identity/me/developer-enrollment", { headers: authHeaders(developerToken, "") }, 200, "developer enrollment read");
  await assertJson(
    "/identity/me/developer-enrollment",
    { method: "POST", headers: authHeaders(developerToken, "") },
    200,
    "developer enrollment write"
  );

  const managedStudios = (await assertJson("/developer/studios", { headers: authHeaders(developerToken, "") }, 200, "managed studios")) as {
    studios: Array<{ id: string }>;
  };
  if (managedStudios.studios.length === 0) {
    throw new Error("Developer managed studios response did not include any managed studios.");
  }

  const uniqueSuffix = Date.now().toString(36);
  const createdStudio = (await assertJson(
    "/studios",
    {
      method: "POST",
      headers: authHeaders(developerToken),
      body: JSON.stringify({
        slug: `workers-smoke-${uniqueSuffix}`,
        displayName: "Workers Smoke Studio",
        description: "Temporary maintained-stack smoke studio."
      })
    },
    201,
    "studio create"
  )) as { studio: { id: string } };

  const createdStudioId = createdStudio.studio.id;
  let createdTitleId = "";
  let createdReportId = "";
  let secondCreatedReportId = "";
  let releaseUnderTestId = "";

  try {
    await assertJson(
      `/developer/studios/${createdStudioId}`,
      {
        method: "PUT",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          slug: `workers-smoke-${uniqueSuffix}`,
          displayName: "Workers Smoke Studio",
          description: "Updated temporary maintained-stack smoke studio."
        })
      },
      200,
      "studio update"
    );

    await assertJson(`/developer/studios/${createdStudioId}/links`, { headers: authHeaders(developerToken, "") }, 200, "studio links read");
    const createdLink = (await assertJson(
      `/developer/studios/${createdStudioId}/links`,
      {
        method: "POST",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          label: "Docs",
          url: "https://example.invalid/docs"
        })
      },
      201,
      "studio link create"
    )) as { link: { id: string } };

    await assertJson(
      `/developer/studios/${createdStudioId}/links/${createdLink.link.id}`,
      {
        method: "PUT",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          label: "Support",
          url: "https://example.invalid/support"
        })
      },
      200,
      "studio link update"
    );
    await assertJson(
      `/developer/studios/${createdStudioId}/links/${createdLink.link.id}`,
      { method: "DELETE", headers: authHeaders(developerToken, "") },
      204,
      "studio link delete"
    );

    for (const kind of ["logo", "avatar", "banner"] as const) {
      const uploadFile = new File([pngPixel], `${kind}.png`, { type: "image/png" });
      const uploadForm = new FormData();
      uploadForm.set("media", uploadFile);
      await assertJson(
        `/developer/studios/${createdStudioId}/${kind}-upload`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${developerToken}` },
          body: uploadForm
        },
        200,
        `studio ${kind} upload`
      );
    }

    await assertJson(`/developer/studios/${createdStudioId}/titles`, { headers: authHeaders(developerToken, "") }, 200, "studio title list");

    const createdTitle = (await assertJson(
      `/developer/studios/${createdStudioId}/titles`,
      {
        method: "POST",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          slug: `workers-smoke-title-${uniqueSuffix}`,
          contentKind: "game",
          metadata: {
            displayName: "Workers Smoke Title",
            shortDescription: "A temporary smoke title.",
            description: "This title exists so the workers smoke suite can exercise full developer CRUD coverage.",
            genreSlugs: ["utility", "qa"],
            minPlayers: 1,
            maxPlayers: 4,
            ageRatingAuthority: "ESRB",
            ageRatingValue: "E",
            minAgeYears: 6
          }
        })
      },
      201,
      "title create"
    )) as { title: { id: string; currentMetadataRevision: number } };
    createdTitleId = createdTitle.title.id;

    const updatedTitle = (await assertJson(
      `/developer/titles/${createdTitleId}`,
      {
        method: "PUT",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          contentKind: "game",
          visibility: "unlisted"
        })
      },
      200,
      "title update"
    )) as { title: { currentMetadataRevision: number } };
    await assertJson(`/developer/titles/${createdTitleId}`, { headers: authHeaders(developerToken, "") }, 200, "title detail");

    const revisedTitle = (await assertJson(
      `/developer/titles/${createdTitleId}/metadata/current`,
      {
        method: "PUT",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          displayName: "Workers Smoke Title Revised",
          shortDescription: "A revised temporary smoke title.",
          description: "Updated metadata for the workers smoke suite.",
          genreSlugs: ["utility", "qa"],
          minPlayers: 1,
          maxPlayers: 6,
          ageRatingAuthority: "ESRB",
          ageRatingValue: "E10+",
          minAgeYears: 10
        })
      },
      200,
      "title metadata upsert"
    )) as { title: { currentMetadataRevision: number } };

    await assertJson(`/developer/titles/${createdTitleId}/metadata-versions`, { headers: authHeaders(developerToken, "") }, 200, "title metadata versions");
    await assertJson(
      `/developer/titles/${createdTitleId}/metadata-versions/${revisedTitle.title.currentMetadataRevision}/activate`,
      { method: "POST", headers: authHeaders(developerToken, "") },
      200,
      "title metadata activate"
    );

    await assertJson(`/developer/titles/${createdTitleId}/media`, { headers: authHeaders(developerToken, "") }, 200, "title media list");
    await assertJson(
      `/developer/titles/${createdTitleId}/media/card`,
      {
        method: "PUT",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          sourceUrl: "https://example.invalid/workers-card.png",
          altText: "Workers card art",
          mimeType: "image/png",
          width: 900,
          height: 1280
        })
      },
      200,
      "title media upsert"
    );

    const heroUploadFile = new File([pngPixel], "hero.png", { type: "image/png" });
    const heroUploadForm = new FormData();
    heroUploadForm.set("media", heroUploadFile);
    heroUploadForm.set("altText", "Workers hero art");
    await assertJson(
      `/developer/titles/${createdTitleId}/media/hero/upload`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${developerToken}` },
        body: heroUploadForm
      },
      200,
      "title media upload"
    );
    await assertJson(
      `/developer/titles/${createdTitleId}/media/hero`,
      { method: "DELETE", headers: authHeaders(developerToken, "") },
      204,
      "title media delete"
    );

    await assertJson(`/developer/titles/${createdTitleId}/releases`, { headers: authHeaders(developerToken, "") }, 200, "title releases list");
    const createdRelease = (await assertJson(
      `/developer/titles/${createdTitleId}/releases`,
      {
        method: "POST",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          version: "0.1.0-smoke",
          status: "testing",
          acquisitionUrl: "https://example.invalid/releases/0.1.0-smoke"
        })
      },
      201,
      "title release create"
    )) as { release: { id: string } };
    const rollbackReleaseId = createdRelease.release.id;

    const createdSecondRelease = (await assertJson(
      `/developer/titles/${createdTitleId}/releases`,
      {
        method: "POST",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          version: "0.1.1-smoke",
          status: "production",
          acquisitionUrl: "https://example.invalid/releases/0.1.1-smoke"
        })
      },
      201,
      "second title release create"
    )) as { release: { id: string } };
    releaseUnderTestId = createdSecondRelease.release.id;

    const releasesAfterSecondCreate = (await assertJson(
      `/developer/titles/${createdTitleId}/releases`,
      { headers: authHeaders(developerToken, "") },
      200,
      "title releases list after second create"
    )) as { releases: Array<{ id: string; version: string }> };
    const releaseVersions = releasesAfterSecondCreate.releases.map((release) => release.version);
    if (!releaseVersions.includes("0.1.0-smoke") || !releaseVersions.includes("0.1.1-smoke")) {
      throw new Error("Title releases list did not preserve both release versions after creating a second release.");
    }

    await assertJson(
      `/developer/titles/${createdTitleId}/releases/${releaseUnderTestId}`,
      {
        method: "PUT",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          version: "0.1.1-smoke",
          status: "production",
          acquisitionUrl: "https://example.invalid/releases/0.1.1-smoke"
        })
      },
      200,
      "title release update"
    );
    await assertJson(
      `/developer/titles/${createdTitleId}/releases/${rollbackReleaseId}/activate`,
      { method: "POST", headers: authHeaders(developerToken, "") },
      200,
      "title release rollback activate"
    );
    await assertJson(
      `/developer/titles/${createdTitleId}/activate`,
      { method: "POST", headers: authHeaders(developerToken, "") },
      200,
      "title activate"
    );
    await assertJson(
      `/developer/titles/${createdTitleId}/archive`,
      { method: "POST", headers: authHeaders(developerToken, "") },
      200,
      "title archive"
    );
    await assertJson(
      `/developer/titles/${createdTitleId}/unarchive`,
      { method: "POST", headers: authHeaders(developerToken, "") },
      200,
      "title unarchive"
    );
    results.push({
      ok: true,
      label: "developer studio and title flows",
      detail: "studio CRUD, links, uploads, title CRUD, lifecycle actions, metadata, media, and release flows succeeded"
    });

    const createdPlayerReport = (await assertJson(
      "/player/reports",
      {
        method: "POST",
        headers: authHeaders(playerToken),
        body: JSON.stringify({
          titleId: createdTitleId,
          reason: `Workers smoke report ${uniqueSuffix}`
        })
      },
      201,
      "player report create"
    )) as { report: { id: string } };
    createdReportId = createdPlayerReport.report.id;

    const createdSecondPlayerReport = (await assertJson(
      "/player/reports",
      {
        method: "POST",
        headers: authHeaders(playerToken),
        body: JSON.stringify({
          titleId: createdTitleId,
          reason: `Workers smoke report secondary ${uniqueSuffix}`
        })
      },
      201,
      "player second report create"
    )) as { report: { id: string } };
    secondCreatedReportId = createdSecondPlayerReport.report.id;

    await assertJson("/player/reports", { headers: authHeaders(playerToken, "") }, 200, "player report list");
    await assertJson(`/player/reports/${createdReportId}`, { headers: authHeaders(playerToken, "") }, 200, "player report detail");
    await assertJson(
      `/player/reports/${createdReportId}/messages`,
      {
        method: "POST",
        headers: authHeaders(playerToken),
        body: JSON.stringify({
          message: "Workers smoke player follow-up."
        })
      },
      200,
      "player report message"
    );

    await assertJson(`/developer/titles/${createdTitleId}/reports`, { headers: authHeaders(developerToken, "") }, 200, "developer report list");
    await assertJson(
      `/developer/titles/${createdTitleId}/reports/${createdReportId}`,
      { headers: authHeaders(developerToken, "") },
      200,
      "developer report detail"
    );
    await assertJson(
      `/developer/titles/${createdTitleId}/reports/${createdReportId}/messages`,
      {
        method: "POST",
        headers: authHeaders(developerToken),
        body: JSON.stringify({
          message: "Workers smoke developer follow-up."
        })
      },
      200,
      "developer report message"
    );
    results.push({
      ok: true,
      label: "player and developer report flows",
      detail: "player report creation and developer report response succeeded"
    });
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

    await assertJson("/moderation/title-reports", { headers: authHeaders(moderatorToken, "") }, 200, "moderation report list");
    if (createdReportId) {
      await assertJson(
        `/moderation/title-reports/${createdReportId}`,
        { headers: authHeaders(moderatorToken, "") },
        200,
        "moderation report detail"
      );
      await assertJson(
        `/moderation/title-reports/${createdReportId}/messages`,
        {
          method: "POST",
          headers: authHeaders(moderatorToken),
          body: JSON.stringify({
            message: "Workers smoke moderation follow-up.",
            recipientRole: "developer"
          })
        },
        200,
        "moderation report message"
      );
      await assertJson(
        `/moderation/title-reports/${createdReportId}/validate`,
        {
          method: "POST",
          headers: authHeaders(moderatorToken),
          body: JSON.stringify({
            note: "Validated by workers smoke."
          })
        },
        200,
        "moderation report validate"
      );
    }
    if (secondCreatedReportId) {
      await assertJson(
        `/moderation/title-reports/${secondCreatedReportId}/invalidate`,
        {
          method: "POST",
          headers: authHeaders(moderatorToken),
          body: JSON.stringify({
            note: "Invalidated by workers smoke."
          })
        },
        200,
        "moderation report invalidate"
      );
    }
    results.push({
      ok: true,
      label: "moderation flows",
      detail: "developer verification and title-report moderation flows succeeded"
    });
  } finally {
    if (createdStudioId) {
      await assertJson(
        `/developer/studios/${createdStudioId}`,
        {
          method: "DELETE",
          headers: authHeaders(developerToken, "")
        },
        204,
        "studio delete"
      );
    }
  }

  for (const result of results) {
    console.log(`PASS ${result.label} (${result.detail})`);
  }
}

run().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exitCode = 1;
});
