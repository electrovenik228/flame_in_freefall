import type { CriterionKey, RankingRow } from "./api";

export const CRITERIA: CriterionKey[] = ["atmosphere", "fuel", "safety", "flow", "gravity"];
export const DEFAULT_WEIGHTS: Record<CriterionKey, number> = { atmosphere: 30, fuel: 25, safety: 20, flow: 15, gravity: 10 };
export const SERIES_CLASS: Record<CriterionKey, string> = {
  atmosphere: "bg-series-1",
  fuel: "bg-series-2",
  safety: "bg-series-3",
  flow: "bg-series-4",
  gravity: "bg-series-5",
};

export interface Scored extends RankingRow {
  points: Record<CriterionKey, number | null>;
}

/**
 * Same rule as the server (section 7.4): the total is rescaled over the criteria that have a
 * score, so a missing value never counts as zero. Runs in the browser when weights change.
 */
export function rescore(rows: RankingRow[], weights: Record<CriterionKey, number>): Scored[] {
  const scored = rows.map((row) => {
    const usable = CRITERIA.filter((key) => row.sub_scores[key].status === "scored" && weights[key] > 0);
    const weightSum = usable.reduce((sum, key) => sum + weights[key], 0);
    const points = Object.fromEntries(CRITERIA.map((key) => [key, null])) as Record<CriterionKey, number | null>;
    let total: number | null = null;
    if (weightSum > 0) {
      total = 0;
      for (const key of usable) {
        points[key] = (100 * weights[key] * (row.sub_scores[key].score ?? 0)) / weightSum;
        total += points[key]!;
      }
    }
    return { ...row, total, points };
  });
  scored.sort((a, b) => {
    if (a.total === null || b.total === null) return a.total === null ? (b.total === null ? 0 : 1) : -1;
    return b.total - a.total || a.psi_id.localeCompare(b.psi_id, undefined, { numeric: true });
  });
  return scored.map((row, index) => ({ ...row, rank: index + 1 }));
}

/** One sentence on what holds a record back: its weakest scored criteria and the ones without data. */
export function whyLow(row: Scored): string {
  const scored = CRITERIA.filter((key) => row.sub_scores[key].status === "scored" && row.points[key] !== null);
  const weak = scored
    .filter((key) => (row.sub_scores[key].score ?? 0) < 0.6)
    .sort((a, b) => (row.sub_scores[a].score ?? 0) - (row.sub_scores[b].score ?? 0))
    .slice(0, 2)
    .map((key) => `${row.sub_scores[key].label.toLowerCase()} scores ${Math.round((row.sub_scores[key].score ?? 0) * 100)}%`);
  const missing = CRITERIA.filter((key) => row.sub_scores[key].status === "not_available").map((key) => row.sub_scores[key].label.toLowerCase());
  const parts = [];
  if (weak.length) parts.push(`Its ${weak.join(" and its ")}.`);
  if (missing.length) parts.push(`No data for ${missing.join(" and ")}, so the total rests on fewer criteria.`);
  if (!parts.length) parts.push("No criterion scores below 60%; other records simply score higher.");
  return parts.join(" ");
}
