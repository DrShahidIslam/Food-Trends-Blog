import fs from "node:fs/promises";
import path from "node:path";

export async function createStateStore(config) {
  await fs.mkdir(path.dirname(config.statePath), { recursive: true });
  await fs.mkdir(config.assetsDir, { recursive: true });
  await fs.mkdir(config.exportsDir, { recursive: true });

  const state = await loadState(config.statePath);

  return {
    state,
    async save() {
      await fs.writeFile(config.statePath, JSON.stringify(this.state, null, 2));
    },
    hasPost(postId) {
      return Boolean(this.state.posts[String(postId)]);
    },
    hasAsset(assetId) {
      return Boolean(this.state.assets[String(assetId)]);
    },
    hasQueueItem(queueId) {
      return Boolean(this.state.queue[String(queueId)]);
    },
    addPost(record) {
      this.state.posts[String(record.postId)] = record;
    },
    addAsset(asset) {
      this.state.assets[asset.id] = asset;
    },
    addQueueItem(item) {
      this.state.queue[item.id] = item;
    },
    getPendingAssets(limit) {
      return Object.values(this.state.assets)
        .filter((asset) => asset.status === "pending_render")
        .sort((a, b) => {
          const aTime = new Date(a.scheduledFor || a.createdAt).getTime();
          const bTime = new Date(b.scheduledFor || b.createdAt).getTime();
          return aTime - bTime || a.createdAt.localeCompare(b.createdAt);
        })
        .slice(0, limit);
    },
    getDueQueueItems(limit) {
      const now = Date.now();
      return Object.values(this.state.queue)
        .filter((item) => item.status === "draft")
        .filter((item) => new Date(item.scheduledFor).getTime() <= now)
        .sort((a, b) => a.scheduledFor.localeCompare(b.scheduledFor))
        .slice(0, limit);
    },
    getAsset(assetId) {
      return this.state.assets[assetId] || null;
    },
    getAssetsByPostId(postId) {
      return Object.values(this.state.assets).filter((asset) => asset.postId === postId);
    },
    countDueDraftQueueItems() {
      const now = Date.now();
      return Object.values(this.state.queue)
        .filter((item) => item.status === "draft")
        .filter((item) => new Date(item.scheduledFor).getTime() <= now)
        .length;
    }
  };
}

async function loadState(statePath) {
  try {
    const raw = await fs.readFile(statePath, "utf8");
    const parsed = JSON.parse(raw);
    return {
      posts: parsed.posts || {},
      assets: parsed.assets || {},
      queue: parsed.queue || {}
    };
  } catch {
    return {
      posts: {},
      assets: {},
      queue: {}
    };
  }
}
