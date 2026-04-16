export async function printStatus({ state }) {
  const posts = Object.keys(state.state.posts).length;
  const assets = Object.values(state.state.assets);
  const queue = Object.values(state.state.queue);
  const rendered = assets.filter((asset) => asset.status === "rendered").length;
  const pending = assets.filter((asset) => asset.status === "pending_render").length;
  const ready = assets.filter((asset) => asset.status === "ready_to_publish").length;
  const rssReady = assets.filter((asset) => asset.status === "rss_ready").length;
  const csvReady = assets.filter((asset) => asset.status === "csv_ready").length;
  const exported = queue.filter((item) => item.status === "exported").length;
  const draft = queue.filter((item) => item.status === "draft").length;
  const csvExported = queue.filter((item) => item.publishMode === "csv").length;
  const rssExported = queue.filter((item) => item.publishMode === "rss").length;

  console.log(`Posts tracked: ${posts}`);
  console.log(`Assets tracked: ${assets.length}`);
  console.log(`Assets rendered: ${rendered}`);
  console.log(`Assets pending: ${pending}`);
  console.log(`Assets ready to publish: ${ready}`);
  console.log(`Assets CSV ready: ${csvReady}`);
  console.log(`Assets RSS ready: ${rssReady}`);
  console.log(`Queue items: ${queue.length}`);
  console.log(`Queue draft: ${draft}`);
  console.log(`Queue exported: ${exported}`);
  console.log(`Queue exported via CSV: ${csvExported}`);
  console.log(`Queue exported via RSS: ${rssExported}`);
}