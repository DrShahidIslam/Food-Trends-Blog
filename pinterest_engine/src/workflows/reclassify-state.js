import { classifyPost } from "../services/classifier.js";

export async function reclassifyState({ config, state, wordpress }) {
  const posts = await wordpress.fetchRecentPosts();
  const byId = new Map(posts.map((post) => [String(post.id), post]));
  let updated = 0;

  for (const [postId, record] of Object.entries(state.state.posts)) {
    const livePost = byId.get(postId);
    if (!livePost) {
      continue;
    }

    const classification = classifyPost(livePost, config.boards);
    record.language = classification.language;
    record.boardKey = classification.boardKey;
    record.boardName = classification.boardName;
    record.contentType = classification.contentType;
    record.shouldPin = classification.shouldPin;

    for (const asset of Object.values(state.state.assets)) {
      if (String(asset.postId) !== postId) {
        continue;
      }
      if (asset.status === "rss_ready") {
        continue;
      }
      asset.language = classification.language;
      asset.boardKey = classification.boardKey;
      asset.boardName = classification.boardName;
      asset.contentType = classification.contentType;
    }

    for (const item of Object.values(state.state.queue)) {
      if (String(item.postId) !== postId) {
        continue;
      }
      if (item.status !== "draft") {
        continue;
      }
      item.boardName = classification.boardName;
    }

    updated += 1;
  }

  await state.save();
  console.log(`Reclassified ${updated} tracked posts.`);
}
