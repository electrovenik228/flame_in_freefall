import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EChart, useThemeColors, type ChartOption } from "@/components/EChart";
import { Card, Chip, ErrorState, PageHeader, SectionTitle, Skeleton } from "@/components/ui";
import { api, type CoverageBin, type CoverageResponse } from "@/lib/api";
import { fmt, kpaToPsi } from "@/lib/format";

// Ordered count steps, one hue from light to dark (reversed on the dark surface).
const STEPS = [
  { upTo: 2, label: "1–2" },
  { upTo: 10, label: "3–10" },
  { upTo: 30, label: "11–30" },
  { upTo: 100, label: "31–100" },
  { upTo: Infinity, label: "over 100" },
];
const RAMP = {
  light: ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"],
  dark: ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"],
};
const stepOf = (count: number) => STEPS.findIndex((step) => count <= step.upTo);
const AXIS_LABEL: Record<string, string> = { oxygen_pct: "Oxygen", pressure_kpa: "Pressure", flow_speed_cm_s: "Flow speed" };

function binText(bin: CoverageBin, data: CoverageResponse): string {
  const y = `${AXIS_LABEL[data.y.field]} ${fmt(bin.y0)}–${fmt(bin.y1)} ${data.y.unit}`;
  const psi = data.y.field === "pressure_kpa" ? ` (${fmt(kpaToPsi(bin.y0))}–${fmt(kpaToPsi(bin.y1))} psi)` : "";
  return `Oxygen ${fmt(bin.x0)}–${fmt(bin.x1)} %, ${y}${psi}`;
}

export default function Coverage() {
  const [params, setParams] = useSearchParams();
  const y = params.get("y") === "flow_speed_cm_s" ? "flow_speed_cm_s" : "pressure_kpa";
  const showTable = params.get("view") === "table";
  const colors = useThemeColors();
  const { data, error, isPending } = useQuery({ queryKey: ["coverage", y], queryFn: () => api<CoverageResponse>("/coverage/", { y }) });
  const set = (key: string, value: string | null) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    }, { replace: true });

  const option = useMemo<ChartOption | null>(() => {
    if (!data) return null;
    const ramp = colors.dark ? RAMP.dark : RAMP.light;
    const isPressure = data.y.field === "pressure_kpa";
    const lunar = data.environments.find((env) => env.slug === "lunar-habitat");
    const points = isPressure
      ? Object.values(
          data.environments
            .filter((env) => env.oxygen_pct_min != null && env.oxygen_pct_min === env.oxygen_pct_max && env.oxygen_pct_min <= 60)
            .reduce<Record<string, { value: number[]; name: string }>>((groups, env) => {
              const key = `${env.oxygen_pct_min}/${env.pressure_kpa_min}`;
              groups[key] = { value: [env.oxygen_pct_min!, env.pressure_kpa_min!], name: groups[key] ? `${groups[key].name}; ${env.name}` : env.name };
              return groups;
            }, {}),
        )
      : [];
    const xs = [...data.bins.flatMap((bin) => [bin.x0, bin.x1]), ...points.map((point) => point.value[0]), 30];
    const ys = [...data.bins.flatMap((bin) => [bin.y0, bin.y1]), ...points.map((point) => point.value[1])];
    const xMin = Math.floor(Math.min(...xs) / 2) * 2 - 2;
    const xMax = Math.ceil(Math.max(...xs) / 2) * 2 + 2;
    const yMin = isPressure ? Math.max(0, Math.floor(Math.min(...ys) / 20) * 20 - 20) : 0;
    const yMax = Math.ceil(Math.max(...ys) / data.y.bin) * data.y.bin + data.y.bin;
    const axis = { nameTextStyle: { color: colors.muted }, axisLabel: { color: colors.muted }, axisLine: { lineStyle: { color: colors.line } }, splitLine: { lineStyle: { color: colors.line, opacity: 0.5 } } };
    return {
      animation: false,
      grid: { left: 64, right: 24, top: 24, bottom: 56 },
      tooltip: {
        trigger: "item",
        backgroundColor: colors.surface,
        borderColor: colors.line,
        textStyle: { color: colors.text, fontSize: 12 },
        formatter: (item: { seriesName: string; dataIndex: number; name: string; value: number[] }) => {
          if (item.seriesName === "Reference environments") return `<b>${item.name}</b><br/>${fmt(item.value[0])}% oxygen, ${fmt(item.value[1])} kPa (${fmt(kpaToPsi(item.value[1]))} psi)`;
          const bin = data.bins[item.dataIndex];
          if (!bin) return "";
          const sources = bin.investigations.map((inv) => `${inv.name} ${inv.runs}`).join(", ");
          return `<b>${bin.count} test ${bin.count === 1 ? "run" : "runs"}</b><br/>${binText(bin, data)}<br/><span style="color:${colors.muted}">Source: ${sources}</span>`;
        },
      },
      xAxis: { type: "value", name: "Oxygen, % by volume", nameLocation: "middle", nameGap: 32, min: xMin, max: xMax, interval: 4, ...axis },
      yAxis: { type: "value", name: isPressure ? "Pressure, kPa" : "Flow speed, cm/s", nameLocation: "middle", nameGap: 44, min: yMin, max: yMax, ...axis },
      series: [
        {
          name: "Test runs",
          type: "custom",
          data: data.bins.map((bin) => [bin.x0, bin.x1, bin.y0, bin.y1, bin.count]),
          encode: { x: [0, 1], y: [2, 3] },
          renderItem: (_: unknown, apiRef: { value: (i: number) => number; coord: (p: number[]) => number[] }) => {
            const [left, bottom] = apiRef.coord([apiRef.value(0), apiRef.value(2)]);
            const [right, top] = apiRef.coord([apiRef.value(1), apiRef.value(3)]);
            return {
              type: "rect",
              shape: { x: left + 1, y: top + 1, width: Math.max(right - left - 2, 1), height: Math.max(bottom - top - 2, 1), r: 2 },
              style: { fill: ramp[stepOf(apiRef.value(4))] },
              emphasis: { style: { stroke: colors.text, lineWidth: 2 } },
            };
          },
          markArea: lunar
            ? {
                silent: true,
                itemStyle: { color: "transparent", borderColor: colors.warm, borderWidth: 2, borderType: "dashed" },
                label: { color: colors.text, fontSize: 12, position: "insideBottomRight", distance: 6, backgroundColor: colors.surface, padding: [3, 6], borderRadius: 4 },
                data: [[
                  { name: isPressure ? "Lunar habitat window: 30% oxygen or more, 70.3 kPa (10.2 psi) or less" : "Lunar habitat oxygen: 30% or more", xAxis: 30, yAxis: isPressure ? yMin : yMin },
                  { xAxis: xMax, yAxis: isPressure ? 70.3 : yMax },
                ]],
              }
            : undefined,
        },
        {
          name: "Reference environments",
          type: "scatter",
          symbolSize: 12,
          data: points,
          itemStyle: { color: colors.warm, borderColor: colors.surface, borderWidth: 2 },
          label: { show: true, formatter: "{b}", position: "top", color: colors.text, fontSize: 12, distance: 8, backgroundColor: colors.surface, padding: [3, 6], borderRadius: 4 },
          labelLayout: { hideOverlap: false, moveOverlap: "shiftY" },
          z: 5,
        },
      ],
    };
  }, [data, colors]);

  return (
    <>
      <PageHeader
        title="Coverage and gaps"
        lead="Where test conditions exist in the catalogue, and where they do not. Each cell counts test runs; outlines and markers show the exploration atmospheres."
      />
      {error && <ErrorState error={error} />}
      {isPending && <Skeleton className="h-[30rem]" />}
      {data && option && (
        <>
          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div role="group" aria-label="Vertical axis" className="no-print flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted">Oxygen against</span>
                <Chip active={y === "pressure_kpa"} onClick={() => set("y", null)}>Pressure</Chip>
                <Chip active={y === "flow_speed_cm_s"} onClick={() => set("y", "flow_speed_cm_s")}>Flow speed</Chip>
                <span className="ml-3 text-xs text-muted">Show as</span>
                <Chip active={!showTable} onClick={() => set("view", null)}>Chart</Chip>
                <Chip active={showTable} onClick={() => set("view", "table")}>Table</Chip>
              </div>
              <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted" aria-label="Legend: test runs per cell">
                <li>Test runs per cell</li>
                {STEPS.map((step, index) => (
                  <li key={step.label} className="num inline-flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded-sm" style={{ background: (colors.dark ? RAMP.dark : RAMP.light)[index] }} aria-hidden />
                    {step.label}
                  </li>
                ))}
                <li className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded-full border-2 border-surface bg-warm" aria-hidden />
                  Reference environment
                </li>
              </ul>
            </div>
            {showTable ? (
              <div className="max-h-[30rem] overflow-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Test runs per cell of oxygen against {AXIS_LABEL[data.y.field].toLowerCase()}</caption>
                  <thead className="sticky top-0 bg-surface text-xs text-muted">
                    <tr>
                      <th scope="col" className="py-2 pr-4 font-medium">Oxygen, %</th>
                      <th scope="col" className="py-2 pr-4 font-medium">{AXIS_LABEL[data.y.field]}, {data.y.unit}</th>
                      <th scope="col" className="py-2 pr-4 text-right font-medium">Test runs</th>
                      <th scope="col" className="py-2 font-medium">Investigations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.bins.map((bin) => (
                      <tr key={`${bin.x0}-${bin.y0}`} className="border-t border-line/60">
                        <td className="num py-1.5 pr-4">{fmt(bin.x0)}–{fmt(bin.x1)}</td>
                        <td className="num py-1.5 pr-4">{fmt(bin.y0)}–{fmt(bin.y1)}</td>
                        <td className="num py-1.5 pr-4 text-right">{bin.count}</td>
                        <td className="py-1.5">
                          {bin.investigations.map((inv, index) => (
                            <span key={inv.psi_id}>
                              {index > 0 && ", "}
                              <Link to={`/investigations/${inv.psi_id}`} className="hover:text-accent">{inv.name}</Link> <span className="num text-muted">{inv.runs}</span>
                            </span>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EChart option={option} label={`Heatmap of ${data.test_runs_plotted} test runs by oxygen and ${AXIS_LABEL[data.y.field].toLowerCase()}. The table view lists every cell.`} />
            )}
            <p className="mt-3 text-xs text-muted" data-testid="coverage-caption">
              <span className="num">{data.test_runs_plotted}</span> of <span className="num">{data.test_runs_total}</span> test runs are plotted.{" "}
              <span className="num">{data.test_runs_missing_an_axis}</span> lack oxygen or {AXIS_LABEL[data.y.field].toLowerCase()} in their PSI table and cannot be placed. An empty cell means no test run in the catalogue, not a tested zero.
              {y === "pressure_kpa"
                ? " The spacesuit atmosphere (100% oxygen, 29.6 kPa) lies far outside the tested range and is not drawn."
                : " The challenge brief gives no ventilation speed for the reference environments, so only the lunar oxygen range is drawn."}
            </p>
          </Card>

          <section className="mt-6">
            <SectionTitle>Gaps by environment</SectionTitle>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {data.environments.map((env) => (
                <Card key={env.slug} data-testid={`gap-${env.slug}`}>
                  <h3 className="font-semibold">{env.name}</h3>
                  <p className={`mt-1 inline-flex items-center gap-1.5 text-sm ${env.tested ? "text-detection" : "text-warm"}`}>
                    {env.tested ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : <AlertTriangle className="h-4 w-4" aria-hidden />}
                    {env.tested ? `Tested: ${env.test_runs_inside} test runs inside this atmosphere` : "Untested: no test run inside this atmosphere"}
                  </p>
                  <h4 className="mb-1 mt-3 text-xs uppercase text-muted">{env.tested ? "Closest investigations" : "Nearest investigations"}</h4>
                  <ul className="space-y-2 text-sm">
                    {env.nearest.map((item) => (
                      <li key={item.psi_id}>
                        <Link to={`/investigations/${item.psi_id}`} className="font-medium hover:text-accent">{item.display_name}</Link>
                        <span className="num ml-2 text-xs text-muted">match {Math.round(item.atmosphere_score * 100)}%</span>
                        <span className="block text-xs text-muted">{item.explanation}</span>
                      </li>
                    ))}
                  </ul>
                  <Link to={`/ranking?env=${env.slug}`} className="mt-3 inline-block text-sm text-accent hover:underline">Full ranking for this environment</Link>
                </Card>
              ))}
              <Card className="border-warm/50" data-testid="partial-gravity">
                <h3 className="font-semibold">Partial gravity: no data</h3>
                <p className="mt-1 text-sm">{data.partial_gravity.statement}</p>
                <h4 className="mb-1 mt-3 text-xs uppercase text-muted">Records that can bound it</h4>
                <ul className="space-y-1 text-sm">
                  {data.partial_gravity.bounding_records.map((item) => (
                    <li key={item.psi_id}>
                      <Link to={`/investigations/${item.psi_id}`} className="hover:text-accent">{item.display_name}</Link>
                      <span className="ml-2 text-xs text-muted">
                        {[item.one_g_reference && "refers to 1 g reference tests", item.partial_gravity_proxy && "electric-field proxy"].filter(Boolean).join(", ")}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          </section>
        </>
      )}
    </>
  );
}
