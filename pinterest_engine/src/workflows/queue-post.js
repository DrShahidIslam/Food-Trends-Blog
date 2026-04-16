import { buildKeywordSet, clampText, slugify } from "../lib/text.js";
import { enrichVariantsWithCopy } from "../services/pin-copywriter.js";
import { buildPinPlan, scheduleDate } from "../services/pin-planner.js";
import { classifyPost } from "../services/classifier.js";

const PLAN_KEYS = ["hero", "list", "guide"];

export async function queuePost({ config, state, post, scheduleAnchorDate }) {
  const classification = classifyPost(post, config.boards);
  const keywordSet = buildKeywordSet(post);

  state.addPost({
    postId: post.id,
    title: post.title,
    url: post.url,
    slug: post.slug,
    language: classification.language,
    boardKey: classification.boardKey,
    boardName: classification.boardName,
    shouldPin: classification.shouldPin,
    contentType: classification.contentType,
    featuredImage: post.featuredImage,
    keywordSet,
    discoveredAt: new Date().toISOString()
  });

  if (!classification.shouldPin) {
    return {
      queuedAssets: 0,
      queuedQueueItems: 0,
      skipped: true
    };
  }

  const missingAssetKeys = PLAN_KEYS.filter((key) => !state.hasAsset(buildAssetId(post.id, key)));
  const missingQueueKeys = PLAN_KEYS.filter((key) => !state.hasQueueItem(buildQueueId(post.id, key)));

  if (missingAssetKeys.length === 0 && missingQueueKeys.length === 0) {
    return {
      queuedAssets: 0,
      queuedQueueItems: 0,
      skipped: false
    };
  }

  const resolvedAnchorDate = resolveScheduleAnchorDate({ config, state, post, scheduleAnchorDate });
  const basePlan = buildPinPlan(post, classification, config, { scheduleAnchorDate: resolvedAnchorDate });
  const plans = missingAssetKeys.length > 0
    ? await enrichVariantsWithCopy(post, classification, basePlan, config)
    : basePlan;
  ensureUniqueCopy(plans);
  const plansByKey = new Map(plans.map((plan) => [plan.key, plan]));

  let queuedAssets = 0;
  let queuedQueueItems = 0;

  for (const key of PLAN_KEYS) {
    const plan = plansByKey.get(key);
    if (!plan) {
      continue;
    }

    const assetId = buildAssetId(post.id, key);
    if (!state.hasAsset(assetId)) {
      state.addAsset({
        id: assetId,
        postId: post.id,
        postSlug: slugify(post.slug || post.title),
        postUrl: post.url,
        boardKey: plan.boardKey,
        boardName: plan.boardName,
        variant: plan.key,
        contentType: classification.contentType,
        language: classification.language,
        overlayTitle: plan.overlayTitle,
        overlaySubtitle: plan.overlaySubtitle,
        pinTitle: plan.pinTitle,
        pinDescription: plan.pinDescription,
        primaryKeyword: plan.primaryKeyword,
        supportingKeywords: plan.supportingKeywords,
        searchTags: buildSearchTags(plan, classification),
        featuredImage: post.featuredImage,
        status: "pending_render",
        createdAt: new Date().toISOString(),
        scheduledFor: plan.scheduledFor
      });
      queuedAssets += 1;
    }

    const queueId = buildQueueId(post.id, key);
    if (!state.hasQueueItem(queueId)) {
      state.addQueueItem({
        id: queueId,
        assetId,
        postId: post.id,
        boardName: plan.boardName,
        scheduledFor: plan.scheduledFor,
        status: "draft"
      });
      queuedQueueItems += 1;
    }
  }

  return {
    queuedAssets,
    queuedQueueItems,
    skipped: false
  };
}

function buildAssetId(postId, key) {
  return `${postId}-${key}`;
}

function buildQueueId(postId, key) {
  return `${buildAssetId(postId, key)}-queue`;
}

function buildSearchTags(plan, classification) {
  const seed = [plan.primaryKeyword, ...(plan.supportingKeywords || []), classification.contentType, classification.boardName]
    .filter(Boolean)
    .map((value) => String(value).trim().toLowerCase());

  return [...new Set(seed)].slice(0, 8);
}

function ensureUniqueCopy(plans) {
  if (!Array.isArray(plans) || plans.length === 0) {
    return;
  }

  ensureUniqueField(plans, "overlayTitle", 56);
  ensureUniqueField(plans, "overlaySubtitle", 70);
  ensureUniqueField(plans, "pinTitle", 100);
}

function ensureUniqueField(plans, field, maxLength) {
  const groups = new Map();
  for (const plan of plans) {
    const raw = String(plan[field] || "").trim();
    const key = normalizeText(raw);
    if (!key) {
      continue;
    }
    const list = groups.get(key) || [];
    list.push(plan);
    groups.set(key, list);
  }

  for (const list of groups.values()) {
    if (list.length < 2) {
      continue;
    }
    for (const plan of list) {
      const suffix = variantSuffix(plan.key);
      const raw = String(plan[field] || "").trim();
      const next = suffix && !raw.toLowerCase().includes(suffix.toLowerCase())
        ? `${raw} - ${suffix}`
        : raw;
      plan[field] = clampText(next, maxLength);
    }
  }
}

function variantSuffix(key) {
  if (key === "hero") return "Main pick";
  if (key === "list") return "Quick summary";
  if (key === "guide") return "Quick guide";
  return "";
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function resolveScheduleAnchorDate({ config, state, post, scheduleAnchorDate }) {
  const maxPins = Number.isFinite(config.maxPinsPerDay) ? config.maxPinsPerDay : 15;
  const maxPosts = Number.isFinite(config.maxPostsPerDay) ? config.maxPostsPerDay : 5;
  const base = scheduleAnchorDate || post.date || new Date().toISOString();
  const anchor = new Date(base);
  anchor.setUTCHours(0, 0, 0, 0);

  const stats = buildDailyStats(state);
  for (let offset = 0; offset < 366; offset += 1) {
    const candidate = new Date(anchor);
    candidate.setUTCDate(candidate.getUTCDate() + offset);
    const candidateIso = candidate.toISOString();

    const scheduledDates = [0, 1, 2].map((index) => scheduleDate(candidateIso, index, config));
    if (canScheduleForDates(stats, scheduledDates, post.id, maxPins, maxPosts)) {
      applyScheduleToStats(stats, scheduledDates, post.id);
      return candidateIso;
    }
  }

  return anchor.toISOString();
}

function buildDailyStats(state) {
  const stats = new Map();
  const queue = state.state?.queue || {};
  for (const item of Object.values(queue)) {
    const dayKey = dayKeyFromDate(item.scheduledFor);
    if (!dayKey) {
      continue;
    }
    const entry = stats.get(dayKey) || { pins: 0, posts: new Set() };
    entry.pins += 1;
    if (item.postId) {
      entry.posts.add(item.postId);
    }
    stats.set(dayKey, entry);
  }
  return stats;
}

function canScheduleForDates(stats, dates, postId, maxPins, maxPosts) {
  for (const iso of dates) {
    const dayKey = dayKeyFromDate(iso);
    if (!dayKey) {
      continue;
    }
    const entry = stats.get(dayKey) || { pins: 0, posts: new Set() };
    const nextPins = entry.pins + 1;
    const nextPosts = entry.posts.has(postId) ? entry.posts.size : entry.posts.size + 1;
    if (nextPins > maxPins || nextPosts > maxPosts) {
      return false;
    }
  }
  return true;
}

function applyScheduleToStats(stats, dates, postId) {
  for (const iso of dates) {
    const dayKey = dayKeyFromDate(iso);
    if (!dayKey) {
      continue;
    }
    const entry = stats.get(dayKey) || { pins: 0, posts: new Set() };
    entry.pins += 1;
    entry.posts.add(postId);
    stats.set(dayKey, entry);
  }
}

function dayKeyFromDate(value) {
  if (!value) {
    return null;
  }
  try {
    return new Date(value).toISOString().slice(0, 10);
  } catch {
    return null;
  }
}
