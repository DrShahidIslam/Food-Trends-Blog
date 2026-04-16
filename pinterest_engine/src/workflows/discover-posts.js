import { queuePost } from "./queue-post.js";

export async function discoverPosts({ config, state, wordpress }) {
  const posts = await wordpress.fetchRecentPosts();
  const cutoff = Date.now() - config.lookbackHours * 60 * 60 * 1000;

  const eligiblePosts = posts
    .filter((post) => post.status === "publish")
    .filter((post) => new Date(post.date).getTime() >= cutoff)
    .filter((post) => !state.hasPost(post.id))
    .slice(0, config.postsPerRun);

  if (eligiblePosts.length === 0) {
    console.log("No new posts discovered.");
    return;
  }

  for (const post of eligiblePosts) {
    const result = await queuePost({ config, state, post });
    if (result.skipped) {
      console.log(`Skipped ${post.id}: ${post.title}`);
      continue;
    }

    if (result.queuedAssets === 0 && result.queuedQueueItems === 0) {
      console.log(`Already queued ${post.id}: ${post.title}`);
      continue;
    }

    console.log(`Queued 3 pins for ${post.id}: ${post.title}`);
  }

  await state.save();
}
