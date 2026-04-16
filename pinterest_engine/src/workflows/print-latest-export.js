import fs from "node:fs/promises";
import path from "node:path";

export async function printLatestExport({ config }) {
  const entries = await safeReadExports(config.exportsDir);
  const csvFiles = entries
    .filter((entry) => entry.isFile())
    .filter((entry) => entry.name.toLowerCase().endsWith(".csv"))
    .sort((a, b) => b.name.localeCompare(a.name));

  if (csvFiles.length === 0) {
    console.log("No CSV exports found.");
    return;
  }

  const latest = csvFiles[0];
  const latestPath = path.join(config.exportsDir, latest.name);
  console.log(`Latest CSV export: ${latestPath}`);
}

async function safeReadExports(exportsDir) {
  try {
    return await fs.readdir(exportsDir, { withFileTypes: true });
  } catch {
    return [];
  }
}