export async function refreshPinterestGalleries({ config, state, wordpress }) {
  const assets = Object.values(state.state.assets || {})
    .filter((asset) => asset.mediaUrl);

  if (assets.length === 0) {
    console.log("No uploaded assets found for gallery refresh.");
    return { updatedPosts: 0, assetCount: 0 };
  }

  const grouped = new Map();
  for (const asset of assets) {
    if (!grouped.has(asset.postId)) {
      grouped.set(asset.postId, []);
    }
    grouped.get(asset.postId).push(asset);
  }

  let updatedPosts = 0;
  for (const [postId, items] of grouped.entries()) {
    const postUrl = items[0]?.postUrl;
    if (!postUrl) {
      continue;
    }

    const result = await wordpress.appendPinterestGallery(postId, postUrl, items);
    if (result.updated) {
      updatedPosts += 1;
    }
  }

  await state.save();
  console.log(`Refreshed Pinterest galleries for ${updatedPosts} posts.`);
  return { updatedPosts, assetCount: assets.length };
}
