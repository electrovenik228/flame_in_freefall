import * as Slider from "@radix-ui/react-slider";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, HelpCircle, Printer, RotateCcw } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AiLabel } from "@/components/Cited";
import { Badge, Button, Card, Chip, DepthBadge, EmptyState, ErrorState, ExternalA, PageHeader, PillarBadge, SectionTitle, Skeleton } from "@/components/ui";
import { api, type CriterionKey, type Environment, type RankingResponse } from "@/lib/api";
import { cn, DATA_DEPTH, fmt, kpaToPsi } from "@/lib/format";
import { CRITERIA, DEFAULT_WEIGHTS, rescore, SERIES_CLASS, whyLow, type Scored } from "@/lib/ranking";

const CUSTOM_KEYS = ["oxygen_pct_min", "oxygen_pct_max", "pressure_kpa_min", "pressure_kpa_max", "flow_cm_s_min", "flow_cm_s_max"] as const;

function atmosphereText(env: Environment): string {
  const oxygen =
    env.oxygen_pct_min != null && env.oxygen_pct_max != null
      ? `${fmt(env.oxygen_pct_min)}% oxygen`
      : env.oxygen_pct_min != null
        ? `${fmt(env.oxygen_pct_min)}% oxygen or more`
        : `${fmt(env.oxygen_pct_max!)}% oxygen or less`;
  const kpa = env.pressure_kpa_max ?? env.pressure_kpa_min!;
  const side = env.pressure_kpa_min == null ? " or less" : env.pressure_kpa_max == null ? " or more" : "";
  return `${oxygen}, ${fmt(kpa)} kPa (${fmt(kpaToPsi(kpa))} psi)${side}, ${env.gravity}`;
}

/** Stacked bar: one segment per criterion, 2px gaps, fixed colour order. The breakdown table is its table view. */
function ScoreBar({ row }: { row: Scored }) {
  const parts = CRITERIA.filter((key) => row.points[key] !== null && row.points[key]! > 0);
  return (
    <div className="flex h-3 w-full gap-[2px] rounded-[4px] bg-surface-2" role="img" aria-label={`Score ${row.total === null ? "not available" : fmt(row.total)} of 100. ${parts.map((key) => `${row.sub_scores[key].label} ${fmt(row.points[key]!)}`).join(", ")}.`}>
      {parts.map((key, index) => (
        <Tooltip.Root key={key}>
          <Tooltip.Trigger asChild>
            <span
              className={cn("h-full", SERIES_CLASS[key], index === 0 && "rounded-l-[4px]", index === parts.length - 1 && "rounded-r-[4px]")}
              style={{ width: `${row.points[key]}%` }}
            />
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content sideOffset={6} className="z-40 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-xl">
              <span className={cn("mr-1.5 inline-block h-2 w-2 rounded-sm", SERIES_CLASS[key])} />
              {row.sub_scores[key].label}: <span className="num">{fmt(row.points[key]!)} points</span>
              <span className="num text-muted"> ({Math.round((row.sub_scores[key].score ?? 0) * 100)}% of weight)</span>
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      ))}
    </div>
  );
}

function Breakdown({ row, weights }: { row: Scored; weights: Record<CriterionKey, number> }) {
  return (
    <div className="mt-4 overflow-x-auto border-t border-line pt-4" data-testid="breakdown">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Score breakdown for {row.display_name}</caption>
        <thead className="text-xs text-muted">
          <tr>
            <th scope="col" className="pb-2 pr-4 font-medium">Criterion</th>
            <th scope="col" className="pb-2 pr-4 text-right font-medium">Weight</th>
            <th scope="col" className="pb-2 pr-4 text-right font-medium">Score</th>
            <th scope="col" className="pb-2 pr-4 text-right font-medium">Points</th>
            <th scope="col" className="pb-2 font-medium">Why, and where it comes from</th>
          </tr>
        </thead>
        <tbody>
          {CRITERIA.map((key) => {
            const sub = row.sub_scores[key];
            return (
              <tr key={key} className="border-t border-line/60 align-top">
                <th scope="row" className="whitespace-nowrap py-2 pr-4 font-normal">
                  <span className={cn("mr-2 inline-block h-2.5 w-2.5 rounded-sm", SERIES_CLASS[key])} aria-hidden />
                  {sub.label}
                </th>
                <td className="num py-2 pr-4 text-right">{weights[key]}</td>
                <td className="num py-2 pr-4 text-right">
                  {sub.status === "scored" ? `${Math.round((sub.score ?? 0) * 100)}%` : <span className="font-sans text-muted">{sub.status === "not_available" ? "Not available" : "Not scored"}</span>}
                </td>
                <td className="num py-2 pr-4 text-right">{row.points[key] === null ? "—" : fmt(row.points[key]!)}</td>
                <td className="py-2 text-muted">
                  <span className="text-text">{sub.explanation}</span>
                  {sub.source.quotes?.map((quote, index) => (
                    <blockquote key={index} className="mt-1 border-l-2 border-accent/60 pl-2 text-xs">“{quote}”</blockquote>
                  ))}
                  <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                    {sub.source.label && <span>{sub.source.label}</span>}
                    {sub.source.psi_url && <ExternalA href={sub.source.psi_url}>{sub.source.psi_id} on PSI</ExternalA>}
                    {sub.source.ai?.model && <AiLabel model={sub.source.ai.model} generatedAt={sub.source.ai.generated_at} />}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t border-line">
            <th scope="row" colSpan={3} className="py-2 pr-4 text-right font-medium">Total, rescaled over the criteria that have a score</th>
            <td className="num py-2 pr-4 text-right font-medium">{row.total === null ? "—" : fmt(row.total)}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function Row({ row, weights }: { row: Scored; weights: Record<CriterionKey, number> }) {
  const [open, setOpen] = useState<"none" | "breakdown" | "why">("none");
  return (
    <li>
      <Card className="p-4" data-testid="ranking-row">
        <div className="grid grid-cols-[2.5rem_minmax(0,1fr)_3.5rem] items-center gap-x-3 gap-y-2 md:grid-cols-[2.5rem_minmax(0,1fr)_minmax(8rem,16rem)_3.5rem]">
          <span className="num text-xl text-muted" aria-label={`Rank ${row.rank}`}>{row.rank}</span>
          <div className="min-w-0">
            <Link to={`/investigations/${row.psi_id}`} className="font-semibold hover:text-accent" title={row.display_name}>
              <span className="line-clamp-1 inline">{row.display_name.length > 70 ? `${row.display_name.slice(0, 68)}…` : row.display_name}</span>
            </Link>
            <span className="num ml-2 text-xs text-muted">{row.psi_id}</span>
          </div>
          <div className="col-span-3 row-start-2 md:col-span-1 md:row-start-auto"><ScoreBar row={row} /></div>
          <span className="num text-right text-xl" data-testid="total">{row.total === null ? "—" : fmt(row.total)}</span>
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 pl-[3.25rem]">
          <div className="flex flex-wrap gap-1.5">
            <DepthBadge depth={row.data_depth} />
            {row.safety_pillars.map((pillar) => <PillarBadge key={pillar} pillar={pillar} />)}
            {row.partial_data && (
              <Badge className="border-warm/50 text-warm" title="At least one criterion has no data for this record. The total is rescaled over the others.">
                <AlertTriangle className="h-3 w-3" aria-hidden />
                Partial data
              </Badge>
            )}
          </div>
          <div className="no-print flex gap-1">
            <Button variant="ghost" aria-expanded={open === "breakdown"} onClick={() => setOpen(open === "breakdown" ? "none" : "breakdown")}>
              <ChevronDown className={cn("h-4 w-4 transition-transform", open === "breakdown" && "rotate-180")} aria-hidden />
              Breakdown
            </Button>
            <Button variant="ghost" aria-expanded={open === "why"} onClick={() => setOpen(open === "why" ? "none" : "why")}>
              <HelpCircle className="h-4 w-4" aria-hidden />
              Why is this ranked {row.rank <= 3 ? "here" : "low"}?
            </Button>
          </div>
        </div>
        {open === "why" && <p className="mt-3 border-t border-line pt-3 text-sm" data-testid="why">{whyLow(row)}</p>}
        {open !== "none" && <Breakdown row={row} weights={weights} />}
      </Card>
    </li>
  );
}

export default function Ranking() {
  const [params, setParams] = useSearchParams();
  const environments = useQuery({ queryKey: ["environments"], queryFn: () => api<Environment[]>("/environments/") });
  const slug = params.get("env") ?? "lunar-habitat";
  const isCustom = slug === "custom";
  const environment = environments.data?.find((env) => env.slug === slug);
  const custom = Object.fromEntries(CUSTOM_KEYS.map((key) => [key, params.get(key) ?? ""]));
  const customBody = Object.fromEntries(CUSTOM_KEYS.filter((key) => custom[key] !== "").map((key) => [key, Number(custom[key])]));
  const customReady = isCustom && ["oxygen_pct_min", "oxygen_pct_max", "pressure_kpa_min", "pressure_kpa_max"].some((key) => key in customBody);
  const [draft, setDraft] = useState(custom);

  const weights = Object.fromEntries(CRITERIA.map((key) => [key, Number(params.get(`w_${key}`) ?? DEFAULT_WEIGHTS[key])])) as Record<CriterionKey, number>;
  const depth = params.get("depth") ?? "";
  const update = (changes: Record<string, string | null>) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === "") next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );

  const ranking = useQuery({
    queryKey: ["ranking", isCustom ? customBody : environment?.id],
    queryFn: () =>
      isCustom
        ? api<RankingResponse>("/rankings/custom/", undefined, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(customBody) })
        : api<RankingResponse>(`/environments/${environment!.id}/ranking/`),
    enabled: isCustom ? customReady : Boolean(environment),
  });
  // Weights are applied in the browser; changing them makes no request (section 8.1).
  const rows = useMemo(() => (ranking.data ? rescore(ranking.data.results, weights) : []), [ranking.data, JSON.stringify(weights)]); // eslint-disable-line react-hooks/exhaustive-deps
  const visible = depth ? rows.filter((row) => row.data_depth === depth) : rows;
  const weightsChanged = CRITERIA.some((key) => weights[key] !== DEFAULT_WEIGHTS[key]);
  const flowScored = rows.some((row) => row.sub_scores.flow.status !== "not_applicable");
  const input = "num w-24 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm";

  const applyCustom = (event: FormEvent) => {
    event.preventDefault();
    update({ env: "custom", ...Object.fromEntries(CUSTOM_KEYS.map((key) => [key, draft[key] || null])) });
  };

  return (
    <Tooltip.Provider delayDuration={100}>
      <PageHeader
        title="Environment ranking"
        lead="Pick a crew environment. Investigations are ranked by an open rubric: measurable parts are computed from PSI data, two parts are judged by AI with quoted evidence."
        actions={<Button onClick={() => window.print()}><Printer className="h-4 w-4" aria-hidden />Print report</Button>}
      />

      <Card className="mb-5">
        <div role="group" aria-label="Crew environment" className="flex flex-wrap gap-2">
          {environments.data?.map((env) => (
            <Chip key={env.slug} active={slug === env.slug} onClick={() => update({ env: env.slug })}>{env.name}</Chip>
          ))}
          <Chip active={isCustom} onClick={() => update({ env: "custom" })}>Custom atmosphere</Chip>
        </div>
        {environment && (
          <p className="mt-3 text-sm" data-testid="environment-summary">
            <span className="num">{atmosphereText(environment)}</span>
            <span className="ml-2 text-muted">
              Source: {environment.source_url ? <ExternalA href={environment.source_url}>{environment.source}</ExternalA> : environment.source}.
            </span>
          </p>
        )}
        {isCustom && (
          <form onSubmit={applyCustom} className="mt-4 flex flex-wrap items-end gap-3">
            {([
              ["oxygen_pct_min", "Oxygen from, %"], ["oxygen_pct_max", "Oxygen to, %"], ["pressure_kpa_min", "Pressure from, kPa"],
              ["pressure_kpa_max", "Pressure to, kPa"], ["flow_cm_s_min", "Flow from, cm/s"], ["flow_cm_s_max", "Flow to, cm/s"],
            ] as const).map(([key, label]) => (
              <label key={key} className="flex flex-col gap-1 text-xs text-muted">
                {label}
                <input type="number" step="any" min={0} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} className={input} />
              </label>
            ))}
            <Button variant="primary" type="submit">Rank for this atmosphere</Button>
            <p className="w-full text-xs text-muted">Leave a field empty for an open bound. A custom atmosphere is ranked entirely in code, with no AI call.</p>
          </form>
        )}
      </Card>

      <div className="grid gap-5 xl:grid-cols-[1fr_20rem]">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
              {CRITERIA.map((key) => (
                <li key={key} className="inline-flex items-center gap-1.5">
                  <span className={cn("h-2.5 w-2.5 rounded-sm", SERIES_CLASS[key])} aria-hidden />
                  {ranking.data?.criteria[key] ?? key}
                </li>
              ))}
            </ul>
            <div role="group" aria-label="Data depth" className="no-print flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted">Data depth</span>
              {Object.entries(DATA_DEPTH).filter(([value]) => value !== "telemetry").map(([value, { label }]) => (
                <Chip key={value} active={depth === value} onClick={() => update({ depth: depth === value ? null : value })}>{label}</Chip>
              ))}
            </div>
          </div>

          {isCustom && !customReady && <EmptyState title="Enter an atmosphere">Give at least one oxygen or pressure bound above, then choose “Rank for this atmosphere”.</EmptyState>}
          {ranking.isError && <ErrorState error={ranking.error} />}
          {ranking.isLoading && <div className="space-y-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-20" />)}</div>}
          {ranking.data && visible.length === 0 && <EmptyState title="No investigation has this data depth">Clear the data-depth filter to see the full ranking.</EmptyState>}
          <ol className="space-y-3" data-testid="ranking-list">
            {visible.map((row) => <Row key={row.psi_id} row={row} weights={weights} />)}
          </ol>
        </div>

        <aside className="space-y-5">
          <Card className="no-print">
            <SectionTitle aside={weightsChanged && (
              <button type="button" onClick={() => update(Object.fromEntries(CRITERIA.map((key) => [`w_${key}`, null])))} className="inline-flex items-center gap-1 text-xs text-accent hover:underline">
                <RotateCcw className="h-3 w-3" aria-hidden />Reset
              </button>
            )}>Weights</SectionTitle>
            <div className="space-y-4">
              {CRITERIA.map((key) => (
                <div key={key}>
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span className="inline-flex items-center gap-2">
                      <span className={cn("h-2.5 w-2.5 rounded-sm", SERIES_CLASS[key])} aria-hidden />
                      {ranking.data?.criteria[key] ?? key}
                    </span>
                    <span className="num text-muted">{weights[key]}</span>
                  </div>
                  <Slider.Root
                    value={[weights[key]]}
                    min={0}
                    max={50}
                    step={5}
                    onValueChange={([value]) => update({ [`w_${key}`]: value === DEFAULT_WEIGHTS[key] ? null : String(value) })}
                    className="relative flex h-5 w-full touch-none select-none items-center"
                  >
                    <Slider.Track className="relative h-1 grow rounded-full bg-surface-2">
                      <Slider.Range className="absolute h-full rounded-full bg-muted" />
                    </Slider.Track>
                    <Slider.Thumb aria-label={`${ranking.data?.criteria[key] ?? key} weight`} className="block h-4 w-4 rounded-full border-2 border-bg bg-text shadow" />
                  </Slider.Root>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-muted">Changing a weight re-orders the list in your browser. The link in the address bar keeps your weights.</p>
          </Card>
          <Card className="space-y-3 text-sm">
            <SectionTitle>Read this first</SectionTitle>
            <p>{ranking.data?.disclaimer ?? "This ranking is a research aid, not a safety rating."}</p>
            <p className="text-muted">{ranking.data?.gravity_note}</p>
            {ranking.data && !flowScored && (
              <p className="text-muted">Flow match is not scored for this environment: the challenge brief gives no ventilation speed. Enter a flow window under Custom atmosphere to score it.</p>
            )}
            <p className="text-muted">Data depth is shown as a badge and a filter. It is not part of the score. <Link to="/about" className="text-accent hover:underline">How the rubric works</Link></p>
          </Card>
        </aside>
      </div>
    </Tooltip.Provider>
  );
}
