import { renderAsset } from "../services/asset-renderer.js";
import { resolveImageSource } from "../services/image-source.js";

export async function renderPendingAssets({ config, state }) {
  const assets = state.getPendingAssets(config.renderBatchSize);
  if (assets.length === 0) {
    console.log("No pending assets to render.");
    return { renderedCount: 0 };
  }

  for (const asset of assets) {
    const siblingAssets = state.getAssetsByPostId
      ? state.getAssetsByPostId(asset.postId)
      : Object.values(state.state.assets || {}).filter((item) => item.postId === asset.postId);
    const usedUrls = siblingAssets
      .filter((item) => item.id !== asset.id)
      .map((item) => item.imageSourceUrl)
      .filter(Boolean);
    if (!asset.imageSourceUrl) {
      const imageSource = await resolveImageSource(asset, config, { excludeUrls: usedUrls, allowFallback: true });
      if (imageSource) {
        asset.imageSourceUrl = imageSource.url;
        asset.imageSourceProvider = imageSource.provider;
        asset.imageSourceAttribution = imageSource.attribution || "";
        asset.imageSourcePage = imageSource.sourcePage || "";
        if (usedUrls.includes(imageSource.url)) {
          asset.imageSourceDuplicate = true;
          console.log(`Duplicate image fallback for ${asset.id} -> ${imageSource.url}`);
        }
      } else if (asset.featuredImage && usedUrls.includes(asset.featuredImage)) {
        asset.imageSourceDuplicate = true;
        console.log(`Duplicate featured image fallback for ${asset.id}`);
      }
    }

    const outputPath = await renderAsset(asset, config);
    asset.outputPath = outputPath;
    asset.status = "rendered";
    asset.renderedAt = new Date().toISOString();
    console.log(`Rendered ${asset.id} -> ${outputPath}`);
  }

  await state.save();
  return { renderedCount: assets.length };
}
