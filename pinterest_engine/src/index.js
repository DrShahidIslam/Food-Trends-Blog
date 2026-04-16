import { loadConfig } from "./lib/config.js";
import { createStateStore } from "./lib/state-store.js";
import { createWordPressClient } from "./services/wordpress-client.js";
import { buildFeedPlan } from "./services/feed-planner.js";
import { backfillPosts } from "./workflows/backfill-posts.js";
import { discoverPosts } from "./workflows/discover-posts.js";
import { renderPendingAssets } from "./workflows/render-assets.js";
import { publishDueQueue } from "./workflows/publish-queue.js";
import { runBotCycle } from "./workflows/run-cycle.js";
import { printStatus } from "./workflows/print-status.js";
import { printLatestExport } from "./workflows/print-latest-export.js";
import { reclassifyState } from "./workflows/reclassify-state.js";
import { refreshPinterestGalleries } from "./workflows/refresh-galleries.js";

async function main() {
  const command = process.argv[2] || "discover";
  const config = loadConfig();
  const state = await createStateStore(config);
  const wordpress = createWordPressClient(config);

  if (command === "discover") {
    await discoverPosts({ config, state, wordpress });
    return;
  }

  if (command === "run") {
    await runBotCycle({ config, state, wordpress });
    return;
  }

  if (command === "backfill") {
    await backfillPosts({ config, state, wordpress });
    return;
  }

  if (command === "render") {
    await renderPendingAssets({ config, state });
    return;
  }

  if (command === "publish") {
    await publishDueQueue({ config, state, wordpress });
    return;
  }

  if (command === "plan-feeds") {
    const result = await buildFeedPlan({ config, wordpress });
    console.log(`Feed plan written to ${result.outputPath}`);
    return;
  }

  if (command === "reclassify") {
    await reclassifyState({ config, state, wordpress });
    return;
  }

  if (command === "refresh-galleries") {
    await refreshPinterestGalleries({ config, state, wordpress });
    return;
  }

  if (command === "status") {
    await printStatus({ state });
    return;
  }

  if (command === "latest-export") {
    await printLatestExport({ config });
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});