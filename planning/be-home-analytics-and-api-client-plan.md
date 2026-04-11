# BE Home Analytics And API Client Plan

## Purpose

Define the first maintained plan for:

- minimal, privacy-conscious BE Home usage analytics
- active-session and active-device counting
- fail-fast device identity experiments on real Board hardware
- a reusable BE Home API client layer that can eventually be shared outside the app itself

This plan is intentionally limited to **Board Enthusiasts-owned metrics**, not official platform-wide Board metrics.

## Product Framing

BE Home can provide community-visible momentum without pretending to be an official Board source.

Examples of acceptable public framing:

- `42 players active in BE Home right now`
- `BE Home has seen roughly 1,180 device identities over time`
- `BE Home users active across 9 countries this week`

Examples to avoid:

- `42 Board users active right now`
- `1,180 Boards sold`
- any language that implies BE has authoritative coverage of the full Board ecosystem

## Goals

- Show a trustworthy live BE Home active-user count in:
  - the BE Home app
  - the BE website
- Maintain internal reporting on:
  - countries using BE Home
  - identity-based active-device trends over time
  - estimated distinct BE Home device identities observed over time
- Keep the analytics footprint small enough to avoid obvious privacy concerns.
- Build the analytics transport on top of a reusable BE Home API client layer rather than thin one-off HTTP calls from UI code.

## Non-Goals For V1

- official Board platform reporting
- exact sales estimates for Board hardware
- fine-grained location tracking
- passive collection or public display of individual Board usernames
- a broad event-analytics product inside BE Home

## Terms

- `active now`: a device session whose heartbeat is still fresh inside the configured TTL window
- `DAD`: Daily Active Device Identities
- `WAD`: Weekly Active Device Identities
- `MAD`: Monthly Active Device Identities
- `session`: one running instance of BE Home on one Board until exit, crash, power loss, or timeout
- `device identity`: a stable pseudonymous identifier used to recognize that the same Board has run BE Home before

## Why Presence Beats A Raw Counter

Do not implement active-user tracking as a simple increment on app open and decrement on app exit.

That model will drift because of:

- power loss
- app crashes
- Wi-Fi drops
- process termination without lifecycle callbacks
- app backgrounding or OS interruption

Instead, BE Home should use a **presence model**:

1. Create or upsert a presence record when the app becomes online.
2. Refresh that record on a steady heartbeat while the app remains active and connected.
3. Count a device as active only when `last_seen_at` is newer than a defined TTL window.
4. Attempt a clean disconnect on exit, but never depend on it for correctness.

This keeps the count self-healing after failures.

## Recommended V1 Data Model

### Presence Session

Store a per-launch session record keyed by an ephemeral `session_id`.

Suggested fields:

- `session_id`
- `device_id_hash`
- `surface`
- `started_at`
- `last_seen_at`
- `ended_at`
- `country_code`
- `be_user_id` nullable
- `board_profile_display_name` nullable
- `board_profile_user_id` nullable
- `client_version`
- `app_mode` or `environment`

Recommended defaults:

- `surface = "be_home"`
- heartbeat every `60` seconds
- active TTL between `120` and `180` seconds

### Device Identity

Store a stable pseudonymous device identity separately from the per-launch session.

Suggested fields:

- `device_id_hash`
- `first_seen_at`
- `last_seen_at`
- `first_country_code`
- `last_country_code`
- `last_client_version`

This supports:

- estimated distinct BE Home device identities observed over time
- DAD/WAD/MAD reporting
- trend lines without tying analytics to raw personal identifiers

## Device Identity Strategy

### Preferred Approach

Try to derive a stable device identifier that is available on Board hardware and then hash it before transmission or storage.

Order of preference:

1. Board-supported stable device identifier, if one exists and is permitted for third-party access
2. Android-accessible stable identifier that is available without privileged permissions
3. Locally generated persistent install identifier as fallback

Raw identifiers must **not** be stored server-side.

Recommended server-side representation:

- `device_id_hash = HMAC-SHA256(raw_identifier, BE-controlled-secret)`

That keeps the stored identifier stable for deduplication while avoiding retention of the raw platform ID.

### Real-Device Experiment Matrix

Because Board is Android-based and `bdb` permissions are strict, the right approach is to try what we can on physical Board hardware and fail fast.

Candidate sources to test:

- `Settings.Secure.ANDROID_ID`
- any Board SDK or Board OS identifier surfaced to third-party apps
- a locally generated install identifier stored in app storage

Expected caveats:

- `ANDROID_ID` can change on factory reset and should be treated as directionally stable rather than perfectly durable
- some identifiers may be unavailable or permission-gated
- install-generated IDs will not survive uninstall or data reset

### V1 Recommendation

Ship with this fallback ladder:

1. try Board-specific stable ID if available
2. try `Settings.Secure.ANDROID_ID`
3. fall back to a generated persistent install ID

Direct Wi-Fi and Bluetooth MAC probing should not ship in V1 because modern Android blocks or sanitizes those APIs on non-privileged apps, and the Board tests performed so far returned unusable values.

Do not treat identity-based lifetime counts as literal Board hardware totals while `ANDROID_ID` remains the primary source.

## Country Tracking

Country is acceptable for internal reporting if kept coarse.

Recommended approach:

- derive country server-side from request context if practical
- otherwise accept a simple country code from the client
- do not collect city, precise region, GPS, or network SSID data

Public exposure should be deferred until the team decides which aggregate country views feel safe and useful.

## Board Profile And Username Strategy

This is the most privacy-sensitive part of the proposed analytics.

### V1 Recommendation

Do **not** silently collect and publicly expose active Board usernames.

Reasons:

- BE Home metrics are valuable even without identity disclosure
- current visibility into Board-native identity APIs is unclear
- users may not expect their Board identity to become publicly visible just because they opened BE Home

### Safer Follow-Up Options

- signed-in BE user with linked Board profile only
- explicit opt-in such as `Show my Board profile as online in BE Home`
- private internal-only enrichment first, with no public display

Until that decision is made, `board_profile_display_name` and related fields should remain optional and nullable in the model.

## Public Metrics To Target First

V1 public metrics:

- active BE Home users right now
- defer any public lifetime distinct-device metric until a stronger Board-specific identifier exists or the caveats are explicitly acceptable

V1 internal metrics:

- DAD
- WAD
- MAD
- country distribution
- signed-in versus anonymous session mix
- approximate distinct device identities observed over time

## BE Home API Client Layer

BE Home should stop accumulating thin endpoint-specific HTTP calls inside screen scripts.

The preferred direction is a decoupled API client layer that BE Home consumes as a library.

### Design Goals

- no UI code should know about raw JSON payload shapes
- network transport should be isolated behind interfaces
- DTOs should be shared within the BE Home client layer
- services should be reusable by multiple screens and future apps
- the library should be movable later into its own package with minimal churn

### Suggested Structure

- `be-home/Assets/Scripts/Api/Contracts`
  - request and response DTOs
- `be-home/Assets/Scripts/Api/Http`
  - HTTP transport
  - serialization
  - retry and timeout behavior
- `be-home/Assets/Scripts/Api/Services`
  - typed service interfaces and implementations
- `be-home/Assets/Scripts/Api/Models`
  - app-facing domain models where BE Home should not depend directly on wire DTOs

### First Services To Add

- `IBeHomePresenceService`
  - start or refresh session presence
  - end session best effort
  - query active BE Home metrics
- `IBeHomeMetricsService`
  - fetch public aggregate metrics for display in app UI

Potential later services:

- `IIdentityService`
- `ICatalogService`
- `IBoardProfileService`
- `ISupportService`

## API Shape Recommendation

Keep this internal to BE-owned surfaces first rather than adding it immediately to the maintained public API contract.

Suggested internal routes:

- `POST /internal/be-home/presence`
  - start or refresh a session
- `POST /internal/be-home/presence/end`
  - optional best-effort disconnect
- `GET /internal/be-home/metrics`
  - aggregate metrics for BE Home display

If this later becomes a supported external integration surface, it can graduate into the formal API-first contract after the product shape stabilizes.

## Suggested V1 Rollout

### Phase 1: Board Hardware Spike

- test every realistic device identity source on a physical Board
- record what is actually readable without privileged permissions
- confirm Wi-Fi-online detection behavior on Board
- confirm app lifecycle hooks that can support heartbeat start and best-effort stop

### Phase 2: Minimal Presence Backend

- add internal Worker routes for BE Home presence and aggregate metrics
- store presence sessions plus deduplicated device identities
- compute `active now` using a TTL window rather than a raw counter

### Phase 3: Minimal BE Home Client Layer

- add DTOs
- add transport abstraction
- add a presence service
- move the first networked presence flow out of `MainScreen`

### Phase 4: Public Display

- show live `active now` count in BE Home
- show the same aggregate count on the website
- label the metric clearly as a BE Home metric

### Phase 5: Internal Reporting

- review DAD/WAD/MAD and country reports
- keep lifetime distinct-device counts internal and caveated unless identity quality materially improves

## Success Criteria

- active count heals automatically after crashes or power loss
- duplicate active sessions from the same launch are avoided
- identity-based device trend metrics remain clearly caveated and are never presented as official Board hardware totals
- BE Home UI consumes metrics through a reusable client layer rather than direct ad hoc requests
- public copy makes clear the metrics are BE-owned, not official Board platform totals

## Open Questions

- Which stable identifier, if any, is actually accessible on physical Board hardware?
- Should country be derived exclusively server-side or allowed from the client as fallback?
- What TTL feels right on real hardware and network conditions, especially for users outside the United States?
- Do we ever want public display of a lifetime distinct-device metric before a stronger Board-specific identifier exists?
- Under what explicit consent model, if any, would Board profile visibility become acceptable later?

## Immediate Next Steps

1. Run a physical Board identifier spike and document which ID sources are accessible.
2. Add a BE Home analytics follow-up item to the maintained implementation queue once the preferred identity source is known.
3. Start the BE Home API client layer with presence-specific DTOs and interfaces rather than waiting for a larger rewrite.
