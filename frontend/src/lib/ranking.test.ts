import { describe, expect, it } from "vitest";

import type { RankingRow, SubScore } from "./api";
import { DEFAULT_WEIGHTS, rescore, whyLow } from "./ranking";

const sub = (score: number | null, status: SubScore["status"] = "scored"): SubScore => ({
  label: "Criterion", status, score, weight: 0, points: null, explanation: "", source: {}, details: {},
});
const row = (psi_id: string, scores: Record<string, SubScore>): RankingRow =>
  ({ psi_id, display_name: psi_id, title: "", data_depth: "", fuel_state: "", safety_pillars: [], psi_url: "", total: null, partial_data: false, rank: 0, sub_scores: scores }) as RankingRow;

describe("rescore", () => {
  const full = row("PSI-1", { atmosphere: sub(1), fuel: sub(0.5), safety: sub(0.5), flow: sub(0), gravity: sub(0.6) });
  const partial = row("PSI-2", { atmosphere: sub(1), fuel: sub(null, "not_available"), safety: sub(null, "not_available"), flow: sub(null, "not_applicable"), gravity: sub(0.8) });

  it("adds sub-scores up to the total", () => {
    const [first] = rescore([full], DEFAULT_WEIGHTS);
    expect(first.total).toBeCloseTo(30 + 12.5 + 10 + 0 + 6);
    expect(Object.values(first.points).reduce((a, b) => a! + b!, 0)).toBeCloseTo(first.total!);
  });
  it("rescales over the criteria that have data, never counting a missing value as zero", () => {
    const [first] = rescore([partial], DEFAULT_WEIGHTS);
    expect(first.total).toBeCloseTo((100 * (30 + 8)) / 40);
    expect(first.points.fuel).toBeNull();
  });
  it("re-orders when weights change", () => {
    expect(rescore([full, partial], DEFAULT_WEIGHTS).map((r) => r.psi_id)).toEqual(["PSI-2", "PSI-1"]);
    const fuelOnly = { atmosphere: 0, fuel: 50, safety: 0, flow: 0, gravity: 0 };
    const ranked = rescore([full, partial], fuelOnly);
    expect(ranked[0].psi_id).toBe("PSI-1");
    expect(ranked[1].total).toBeNull();
  });
  it("explains a low rank", () => {
    const [first] = rescore([full], DEFAULT_WEIGHTS);
    expect(whyLow(first)).toContain("scores 0%");
    expect(whyLow(rescore([partial], DEFAULT_WEIGHTS)[0])).toContain("No data for");
  });
});
