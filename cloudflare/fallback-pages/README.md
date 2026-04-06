# Cloudflare Fallback Pages

This folder contains the standalone BE-branded fallback pages that can stay available even when the main SPA, Workers API, or Supabase-backed services are unhealthy.

## Files

- [`index.html`](./index.html): manual maintenance / fallback page
- [`cloudflare/5xx.html`](./cloudflare/5xx.html): branded Cloudflare 500-class error page
- [`cloudflare/1xxx.html`](./cloudflare/1xxx.html): branded Cloudflare 1000-class error page
- [`_headers`](./_headers): cache and indexing headers for the fallback site

## Preview

Deploy a branch preview from the repository root:

```bash
python ./scripts/dev.py deploy-fallback-pages --project-name board-enthusiasts-fallback
```

That command prints the preview URLs you can review before merging.

## Publish

After the branch is reviewed and merged to `main`, redeploy from `main` so the production Pages hostname updates:

```bash
python ./scripts/dev.py deploy-fallback-pages --project-name board-enthusiasts-fallback --source-branch main
```

The stable production URLs then become:

- `https://board-enthusiasts-fallback.pages.dev/`
- `https://board-enthusiasts-fallback.pages.dev/cloudflare/5xx.html`
- `https://board-enthusiasts-fallback.pages.dev/cloudflare/1xxx.html`

## Cloudflare Setup

Use the production URLs above in Cloudflare for two separate protections:

1. Manual maintenance fallback:
   create a disabled temporary redirect rule that sends visitor traffic to the fallback root page.
2. Branded custom error pages:
   point Cloudflare `500 class errors` at `cloudflare/5xx.html` and `1000 class errors` at `cloudflare/1xxx.html`.

Whenever you update either error page, use Cloudflare's `Fetch custom page again` action so Cloudflare refreshes the cached error-page HTML.
