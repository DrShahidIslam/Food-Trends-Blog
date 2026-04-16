import { discoverPosts } from "./discover-posts.js";
import { publishDueQueue } from "./publish-queue.js";
import { renderPendingAssets } from "./render-assets.js";

export async function runBotCycle({ config, state, wordpress }) {
  await discoverPosts({ config, state, wordpress });

  const maxPasses = Math.max(
    1,
    Math.ceil(state.countDueDraftQueueItems() / Math.max(config.publishBatchSize, 1)) + 2
  );

  for (let pass = 1; pass <= maxPasses; pass += 1) {
    const dueBefore = state.countDueDraftQueueItems();
    if (dueBefore === 0) {
      console.log("No due queue backlog remains after discover.");
      return;
    }

    const renderResult = await renderPendingAssets({ config, state });
    const publishResult = await publishDueQueue({ config, state, wordpress });
    const dueAfter = state.countDueDraftQueueItems();

    console.log(
      `Cycle pass ${pass}: due before=${dueBefore}, rendered=${renderResult.renderedCount}, exported=${publishResult.exportedCount}, due after=${dueAfter}`
    );

    if (dueAfter === 0) {
      return;
    }

    if (renderResult.renderedCount === 0 && publishResult.exportedCount === 0) {
      console.log("Cycle stopped because no further render or publish progress was possible.");
      return;
    }
  }

  console.log(`Cycle reached the safety limit with ${state.countDueDraftQueueItems()} due draft items still waiting.`);
}
