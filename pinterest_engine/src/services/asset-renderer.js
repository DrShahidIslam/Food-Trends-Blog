import fs from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import { escapeHtml, wrapText } from "../templates/svg-text.js";

const THEMES = {
  recipe: {
    background: ["#fff0e1", "#ffc98f", "#d87439"],
    hero: "#6c2f12",
    panel: "#fff3e2",
    panelText: "#5d2f15",
    accent: "#9b471d",
    badge: "EASY RECIPE"
  },
  spread: {
    background: ["#f7ead8", "#d8b07b", "#7f4a22"],
    hero: "#4a2817",
    panel: "#f4e4d1",
    panelText: "#4a2c1c",
    accent: "#74401f",
    badge: "SPREAD INSPO"
  },
  trend: {
    background: ["#fff3e8", "#f0c29d", "#cb6e45"],
    hero: "#6a2d1d",
    panel: "#fff0e4",
    panelText: "#5c3426",
    accent: "#aa4b2c",
    badge: "TRENDING SWEET"
  }
};

const VARIANT_LABELS = {
  hero: "Hero Pin",
  list: "Saveable Summary",
  guide: "Quick Guide"
};

export async function renderAsset(asset, config) {
  const theme = THEMES[asset.contentType] || THEMES.trend;
  const fileName = `${asset.postSlug || asset.postId}-${asset.variant}.jpg`;
  const hasFeaturedImage = Boolean(asset.imageSourceUrl || asset.featuredImage);
  const quality = hasFeaturedImage ? 85 : 88;
  const effort = 6;
  const outputPath = path.join(config.assetsDir, "pinterest", fileName);
  const base = sharp({
    create: {
      width: 1000,
      height: 1500,
      channels: 4,
      background: theme.background[0]
    }
  });

  const composites = [];
  const visualBuffer = await loadImageBuffer(asset.imageSourceUrl || asset.featuredImage);

  if (visualBuffer) {
    composites.push({
      input: await sharp(visualBuffer)
        .resize(1000, 1500, { fit: "cover", position: "attention" })
        .blur(2)
        .modulate({ saturation: 1.05, brightness: 0.95 })
        .jpeg({ quality: 82, mozjpeg: true })
        .toBuffer(),
      top: 0,
      left: 0
    });

    composites.push({
      input: Buffer.from(`<svg width="1000" height="1500" xmlns="http://www.w3.org/2000/svg"><rect width="1000" height="1500" fill="rgba(42,25,16,0.04)"/></svg>`),
      top: 0,
      left: 0
    });

    composites.push({
      input: await sharp(visualBuffer)
        .resize(740, 520, { fit: "cover", position: "attention" })
        .modulate({ saturation: 1.08, brightness: 1.02 })
        .jpeg({ quality: 84, mozjpeg: true })
        .toBuffer(),
      top: 180,
      left: 130
    });
  } else {
    composites.push({
      input: Buffer.from(`<svg width="1000" height="1500" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="${theme.background[0]}"/><stop offset="45%" stop-color="${theme.background[1]}"/><stop offset="100%" stop-color="${theme.background[2]}"/></linearGradient></defs><rect width="1000" height="1500" fill="url(#bg)"/></svg>`),
      top: 0,
      left: 0
    });
  }

  const svg = buildOverlaySvg(asset, theme, Boolean(visualBuffer));
  composites.push({ input: Buffer.from(svg), top: 0, left: 0 });

  await fs.mkdir(path.join(config.assetsDir, "pinterest"), { recursive: true });
  await base.composite(composites).jpeg({ quality, mozjpeg: true }).toFile(outputPath);
  return outputPath;
}

function buildOverlaySvg(asset, theme, hasPhoto) {
  if (asset.variant === "list") {
    return buildListOverlay(asset, theme, hasPhoto);
  }

  if (asset.variant === "guide") {
    return buildGuideOverlay(asset, theme, hasPhoto);
  }

  return buildHeroOverlay(asset, theme, hasPhoto);
}

function buildHeroOverlay(asset, theme, hasPhoto) {
  const titleLines = wrapText(asset.overlayTitle, 22, 3);
  const subtitleLines = wrapText(asset.overlaySubtitle, 28, 2);
  const keywordLabel = wrapText(toDisplayCase(asset.primaryKeyword || asset.overlayTitle), 16, 1);

  const titleSvg = titleLines
    .map((line, index) => {
      const y = hasPhoto ? 740 + index * 60 : 330 + index * 90;
      const fill = hasPhoto ? theme.hero : "#fff8f1";
      return `<text x="170" y="${y}" font-size="56" font-family="Georgia, serif" fill="${fill}" font-weight="700">${escapeHtml(line)}</text>`;
    })
    .join("");

  const subtitleSvg = subtitleLines
    .map((line, index) => {
      const y = 920 + index * 30;
      return `<text x="170" y="${y}" font-size="26" font-family="Arial, sans-serif" fill="${theme.panelText}" font-weight="700">${escapeHtml(line)}</text>`;
    })
    .join("");

  const keywordSvg = keywordLabel
    .map((line, index) => `<text x="170" y="${206 + index * 26}" font-size="20" font-family="Arial, sans-serif" fill="#fff7ef" font-weight="700">${escapeHtml(line)}</text>`)
    .join("");

  return `
    <svg width="1000" height="1500" viewBox="0 0 1000 1500" xmlns="http://www.w3.org/2000/svg">
      <rect x="100" y="140" width="800" height="1040" rx="32" fill="#fffaf5" opacity="0.72"/>
      <rect x="130" y="180" width="740" height="520" rx="28" fill="${hasPhoto ? "rgba(255,250,245,0.01)" : theme.hero}"/>
      ${hasPhoto ? `<rect x="130" y="180" width="740" height="520" rx="28" fill="rgba(64,32,18,0.01)"/>` : `<circle cx="770" cy="220" r="170" fill="#ffffff" opacity="0.10"/><circle cx="250" cy="560" r="120" fill="#ffffff" opacity="0.08"/>`}
      <rect x="140" y="170" width="260" height="58" rx="20" fill="${theme.accent}" opacity="0.92"/>
      ${keywordSvg}
      <rect x="130" y="670" width="740" height="360" rx="28" fill="${theme.panel}" opacity="0.75"/>
      ${titleSvg}
      ${subtitleSvg}
      <rect x="170" y="1060" width="660" height="52" rx="26" fill="${theme.accent}"/>
      <text x="500" y="1094" text-anchor="middle" font-size="26" font-family="Arial, sans-serif" fill="#fff8f0" font-weight="700">Read more on el-mordjene.info</text>
    </svg>
  `;
}

function buildListOverlay(asset, theme, hasPhoto) {
  const subtitleLine = wrapText(asset.overlaySubtitle, 26, 1);
  const titleLines = wrapText(asset.overlayTitle, 20, 4);

  const subtitleSvg = subtitleLine
    .map((line) => `<text x="500" y="120" text-anchor="middle" font-size="28" font-family="Georgia, serif" fill="#2b1a12" font-weight="600" letter-spacing="2">${escapeHtml(line)}</text>`)
    .join("");

  const boxHeight = titleLines.length * 70 + 40;
  const startY = 440 - ((titleLines.length - 1) * 70) / 2 + 20;

  const titleSvg = titleLines
    .map((line, index) => `<text x="500" y="${startY + index * 70}" text-anchor="middle" font-size="60" font-family="Arial Black, Arial, sans-serif" fill="#111" font-weight="800">${escapeHtml(line)}</text>`)
    .join("");

  return `
    <svg width="1000" height="1500" viewBox="0 0 1000 1500" xmlns="http://www.w3.org/2000/svg">
      <rect width="1000" height="1500" fill="rgba(255,255,255,0.02)"/>
      <rect x="180" y="85" width="160" height="2" fill="#2b1a12" opacity="0.5"/>
      <rect x="660" y="85" width="160" height="2" fill="#2b1a12" opacity="0.5"/>
      ${subtitleSvg}
      <rect x="160" y="${440 - boxHeight / 2}" width="680" height="${boxHeight}" rx="24" fill="rgba(255,255,255,0.92)"/>
      ${titleSvg}
    </svg>
  `;
}
function buildGuideOverlay(asset, theme, hasPhoto) {
  const titleLines = wrapText(asset.overlayTitle, 18, 2);
  const subtitleLines = wrapText(asset.overlaySubtitle, 26, 1);

  const titleSvg = titleLines
    .map((line, index) => `<text x="500" y="${770 + index * 70}" text-anchor="middle" font-size="64" font-family="Georgia, serif" fill="#fff6ef" font-weight="700">${escapeHtml(line)}</text>`)
    .join("");

  const subtitleSvg = subtitleLines
    .map((line) => `<text x="500" y="${920}" text-anchor="middle" font-size="30" font-family="Arial, sans-serif" fill="#fff6ef" font-weight="600">${escapeHtml(line)}</text>`)
    .join("");

  return `
    <svg width="1000" height="1500" viewBox="0 0 1000 1500" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="680" width="1000" height="360" fill="#8f1f28" opacity="0.95"/>
      ${titleSvg}
      ${subtitleSvg}
      <text x="500" y="990" text-anchor="middle" font-size="28" font-family="Georgia, serif" fill="#fff6ef" font-weight="600">el-mordjene.info</text>
    </svg>
  `;
}
async function loadImageBuffer(url) {
  if (!url) {
    return null;
  }

  try {
    const response = await fetch(url, {
      headers: {
        Accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
      }
    });

    if (!response.ok) {
      return null;
    }

    const arrayBuffer = await response.arrayBuffer();
    return Buffer.from(arrayBuffer);
  } catch {
    return null;
  }
}

function toDisplayCase(value) {
  return String(value || "")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}






























