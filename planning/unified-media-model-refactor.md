# Unified Media Model Refactor

## Why This Needs To Happen Now

Developer feedback has been consistent: BE asks for specific image shapes, but several live surfaces crop, stretch, or reuse those assets in ways that do not match the guidance. The biggest pain points are:

- title detail media clipping at the top and bottom
- quick view using a wide, thin banner treatment that does not match the current title hero slot
- browse cards using square-ish tiles while the current title card slot was previously portrait-oriented
- studio banner/logo/avatar reuse causing the wrong asset shape to appear in the wrong surface
- unclear developer guidance about where each media slot is actually used

Because the product is still early, we should fix the media model now rather than let more content accumulate on top of a confusing foundation.

## Product Decisions Locked In

### Layout and Ratio Rules

- If BE tells a developer to upload a specific ratio, BE must render that ratio consistently.
- Display surfaces may scale up/down across breakpoints, but the surface aspect ratio itself should not change.
- If a surface needs a different aspect ratio, it must use a different media type.

### Title Media

- Add `title_avatar` at `1:1`
- Make `title_card` a true square `1:1`
- Keep `title_logo` as `3:1`
- Remove `title_hero`
- Keep `title_showcase` as repeatable `16:9`
- Add `title_quick_view_banner` at `21:9`

### Title Surface Usage

- `title_avatar`
  - small compact identity spots
  - browse-card identity block beside the title name
  - small quick-view or list identity surfaces when needed
- `title_card`
  - browse result tiles
  - Board-friendly square card surfaces
- `title_logo`
  - large branded title lockups where a horizontal logo is appropriate
- `title_quick_view_banner`
  - the thin wide quick-view media strip
  - if absent, quick view falls back to the first `title_showcase` item
- `title_showcase`
  - gallery screenshots and preview videos
  - the first ordered showcase item becomes the default full title detail hero/media selection

### Studio Media

- `studio_avatar` at `1:1`
- `studio_logo` at `3:1`
- `studio_banner` at `21:9`

### Showcase Ordering

- developers must be able to order showcase items
- the developer console should present showcase media as list items with thumbnails plus metadata
- ordering should be editable with drag/drop in the maintained UI
- the first showcase item becomes the default title detail hero/media selection

## Data Model Direction

We should replace the split media storage model:

- `studios.avatar_url` / `logo_url` / `banner_url`
- `public.title_media_assets`
- `public.title_showcase_media`

with a unified data-driven media model:

1. `media_type_definitions`
   - one row per supported media type
   - stores the maintained user-facing/media-processing metadata
2. `catalog_media_entries`
   - one row per uploaded/linked media item
   - references a media type definition
   - belongs to either a studio or a title
   - supports both single-slot media and repeatable ordered media

### Maintained Media Type Attributes

Each media type definition should include:

- stable key
- owner kind (`studio` or `title`)
- display name
- user-facing description of where the media is used
- aspect ratio width/height
- storage bucket
- maximum upload size
- accepted mime types
- whether the type is repeatable
- whether the type supports external video
- default sort / ordering rules

This gives us one source of truth for:

- API validation
- developer upload UI copy
- preview frame ratios
- storage routing
- future additions without hard-coding more one-off fields

## Target Media Type Set

### Studios

- `studio_avatar`
- `studio_logo`
- `studio_banner`

### Titles

- `title_avatar`
- `title_card`
- `title_logo`
- `title_quick_view_banner`
- `title_showcase`

## Migration Strategy

### Database Migration Goals

- create the new media type definitions table
- create the unified media entries table
- migrate existing studio/title media values into the new table
- preserve current URLs/storage paths during migration
- remap API/backend/frontend reads to the new model
- remove redundant legacy fields and tables after cutover

### Existing Data Mapping

#### Studio Mapping

- `studios.avatar_url` -> `studio_avatar`
- `studios.logo_url` -> `studio_logo`
- `studios.banner_url` -> `studio_banner`

#### Title Mapping

- `title_media_assets.card` -> `title_card`
- `title_media_assets.logo` -> `title_logo`
- `title_media_assets.hero` -> first `title_showcase` image if it is not already represented there
- `title_showcase_media` image/video rows -> `title_showcase`
- no legacy source exists for `title_avatar` or `title_quick_view_banner`, so those begin empty

### Backward-Compatibility Rules During Cutover

- quick view falls back from `title_quick_view_banner` to the first `title_showcase`
- title detail uses the first ordered `title_showcase`
- browse tiles use `title_card`
- if `title_avatar` is absent, compact identity spots may fall back to `title_logo`, then text-only, but should not force a `3:1` logo into a square crop

### Removal Targets After Cutover

- `public.title_media_assets`
- `public.title_showcase_media`
- legacy studio media columns on `public.studios`
- legacy contract fields whose values are directly derived from old storage layout rather than new media entries

## API Direction

Authenticated developers should get full CRUD over the new media entries.

### Needed Authenticated Surfaces

- list available media types for a studio/title owner kind
- list current media entries for a specific studio or title
- create media entry
- update media entry metadata
- upload media binary for a media entry
- delete media entry
- reorder repeatable media entries

### Recommended Endpoint Shape

#### Media Types

- `GET /developer/media-types?ownerKind=studio|title`

#### Studio Media

- `GET /developer/studios/{studioId}/media`
- `POST /developer/studios/{studioId}/media`
- `PUT /developer/studios/{studioId}/media/{mediaEntryId}`
- `POST /developer/studios/{studioId}/media/{mediaEntryId}/upload`
- `DELETE /developer/studios/{studioId}/media/{mediaEntryId}`
- `PUT /developer/studios/{studioId}/media/order`

#### Title Media

- `GET /developer/titles/{titleId}/media`
- `POST /developer/titles/{titleId}/media`
- `PUT /developer/titles/{titleId}/media/{mediaEntryId}`
- `POST /developer/titles/{titleId}/media/{mediaEntryId}/upload`
- `DELETE /developer/titles/{titleId}/media/{mediaEntryId}`
- `PUT /developer/titles/{titleId}/media/order`

## Developer Console UX Direction

Replace the current hand-authored slot panels with a data-driven media manager:

- one unified “Media” area per studio/title
- grouped by media type
- explicit user-facing copy for where each type appears
- exact aspect-ratio preview frame
- file requirements shown from the media type definition
- repeatable items rendered as list rows/cards with thumbnails and metadata
- drag/drop ordering for repeatable media like `title_showcase`

### Copy Expectations

Do not rely on jargon alone. Every media type description should explain usage in plain language, for example:

- `Title card`
  - used on browse tiles and Board catalog cards
- `Title avatar`
  - used in compact title identity spots, such as the small image beside the title name
- `Title quick view banner`
  - used in the wide thin image strip at the top of quick view
- `Studio banner`
  - used at the top of studio pages as the wide studio header image

## Frontend Rendering Follow-Ups

### Title Surfaces

- browse cards should remain square tile surfaces and use `title_card`
- browse-card identity block should use `title_avatar` plus text, replacing the current logo-in-panel pattern
- quick view should use `title_quick_view_banner`, falling back to the first `title_showcase`
- title detail should default to the first `title_showcase`

### Studio Surfaces

- studio detail and studio summary surfaces should use `studio_banner`, `studio_avatar`, and `studio_logo` intentionally rather than mixing them by fallback
- square avatar surfaces should not default to a horizontal logo crop

## Performance Follow-Ups

The media refactor should also improve perceived performance:

- move major surfaces away from CSS `background-image` when possible and prefer real `<img>`
- add placeholder/skeleton frames for media loads
- lazy-load non-critical gallery assets
- use async image decoding
- preload quick-view data/media in the background from visible browse cards
- cache media aggressively in browser and CDN

## Storage Guidance

This refactor may require Supabase storage updates.

### Minimum Viable Storage Path

We can keep the existing buckets initially if needed:

- `avatars`
- `card-images`
- `hero-images`
- `logo-images`

with the new media type definitions pointing into those maintained buckets.

### Recommended Follow-Up

After the new model is fully implemented, review whether bucket names still match actual use. The current `hero-images` bucket especially becomes misleading once `title_hero` is removed and `studio_banner` / `title_quick_view_banner` / `title_showcase` all coexist.

Potential future cleanup:

- keep existing buckets for compatibility if bucket rename cost is too high
- or create clearer buckets later if operationally worthwhile

## Delivery Order

1. Add planning note and lock product decisions
2. Add unified media-type definitions in contract/shared model
3. Add database migration for new media definition + entry tables and migrate current data
4. Add authenticated CRUD endpoints for unified media entries
5. Switch backend read models to use the unified media table
6. Refactor developer media UI to data-driven upload/ordering
7. Refactor browse/title/studio surfaces to consume the new media types
8. Remove legacy media tables/columns/routes once cutover is complete
