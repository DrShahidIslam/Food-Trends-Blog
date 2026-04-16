# Pinterest Autopilot for WordPress

This is a standalone Pinterest automation app for `el-mordjene.info`.
It stays completely separate from the El-Mordjene Alerts App.

The app now does five jobs:
- fetch newly published WordPress posts
- classify each post into the right Pinterest board
- generate 3 planned pins per article
- render vertical Pinterest assets for those queued pins
- upload due assets to WordPress, inject them into posts, and export a publish-ready batch

## Why this path is best

Pinterest officially supports two things that matter here:
- bulk upload with CSV files
- RSS auto-publishing that can create Pins for each image in an RSS item or webpage

That makes the strongest hands-off path:
1. generate 3 pin images per article
2. upload those images to WordPress
3. attach them to the article page
4. let Pinterest RSS ingest them into your claimed account and mapped boards

## Architecture

This app is intentionally separate from article generation.

- `src/services/wordpress-client.js`
  Pulls live published posts from WordPress, uploads rendered pin assets back to WordPress media, and injects a Pinterest gallery into posts.
- `src/services/classifier.js`
  Decides whether a post is Pinterest-worthy and maps it to a board.
- `src/services/pin-planner.js`
  Creates 3 distinct pin variants per article.
- `src/services/pin-copywriter.js`
  Optionally improves pin copy using Gemini.
- `src/services/image-source.js`
  Chooses the best available visual source for a pin: featured image first or free stock from Pexels/Pixabay.
- `src/services/asset-renderer.js`
  Renders vertical `1000x1500` Pinterest graphics with different looks for recipes, spreads, and trends.
- `src/services/exporter.js`
  Exports due pins into CSV and JSON batches.
- `src/lib/state-store.js`
  Stores tracked posts, assets, and queue items in `data/state.json`.

## Current workflow

1. `npm run discover`
   Imports recent posts from WordPress and queues 3 pins for each eligible post.
2. `npm run backfill`
   Finds older untracked published posts and schedules them gradually for a safe backlog catch-up.
3. `npm run render`
   Resolves a visual source for each queued pin and renders Pinterest graphics into `data/assets`.
4. `npm run publish`
   Uploads due rendered images to WordPress, injects the 3-pin gallery into the source post, and exports a CSV and JSON batch into `data/exports`.
5. `npm run status`
   Prints the current state summary.

## Board mapping

The app currently routes posts into these boards:
- `Recipes`
- `Recettes`
- `Spreads`
- `Pates a tartiner`
- `Sweets & Trends`

Routing is based on language plus content signals like recipe and spread keywords.

## Image strategy

The renderer now uses a hybrid image pipeline:
1. post featured image
2. Pexels stock image if configured
3. Pixabay stock image if configured
4. branded template fallback

Set `IMAGE_SOURCE_MODE=featured-first` to keep your own article image as the default.
Set `IMAGE_SOURCE_MODE=stock-first` if you want the app to prefer stock photos whenever it finds one.

## What publish means now

When a pin is due, the app:
- uploads the image to WordPress media
- appends a Pinterest gallery block to the post
- marks the asset as RSS-ready
- exports the same batch as CSV and JSON for backup or manual bulk import

This gives you two paths at once:
- official RSS auto-publish for hands-off automation
- bulk import backup if needed

## Important Pinterest setup

For best results, connect multiple RSS feeds to boards in Pinterest Business settings.
Each feed can map to a different board.

## Environment variables

Copy `.env.example` into your runtime secret setup and provide:
- `SITE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`
- `GEMINI_API_KEY` optional
- `GEMINI_TEXT_MODEL` optional
- `PEXELS_API_KEY` optional
- `PIXABAY_API_KEY` optional
- `IMAGE_SOURCE_MODE` optional
- `POSTS_PER_RUN`
- `LOOKBACK_HOURS`
- `BACKFILL_POSTS_PER_RUN`
- `BACKFILL_MAX_PAGES`
- `BACKFILL_START_DELAY_HOURS`
- `BACKFILL_POST_INTERVAL_HOURS`
- `RENDER_BATCH_SIZE`
- `PUBLISH_BATCH_SIZE`
- `PIN_DAY_1`
- `PIN_DAY_2`
- `PIN_DAY_3`
- board name variables if you want custom names

## Cloud execution

Use GitHub Actions so it runs while your laptop is off.

The included workflow does three things every run:
- discovers new posts
- renders pending pin assets
- uploads and injects due assets into posts

## Safe backfill strategy

Use `npm run backfill` for older posts you want to catch up on without spamming Pinterest.

- it only targets older posts that are not already tracked in `data/state.json`
- it will not recreate existing asset ids or queue items if you rerun it
- it starts scheduling in the future using `BACKFILL_START_DELAY_HOURS`
- it spaces each backfilled post using `BACKFILL_POST_INTERVAL_HOURS`

With the defaults, the app begins backfilled publishing 24 hours later and only introduces one new backfilled post every 24 hours.

## Notes

This is now aligned with the strongest official Pinterest automation route.
For image quality, free stock plus strong text overlays is more reliable than depending on free AI image generation every day.

