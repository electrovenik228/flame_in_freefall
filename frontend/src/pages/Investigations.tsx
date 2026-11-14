import { useQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, LayoutGrid, Table2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Badge, Button, Card, Chip, DepthBadge, EmptyState, ErrorState, Metric, PageHeader, PILLARS, PillarBadge, Skeleton } from "@/components/ui";
import { api, type Facility, type InvestigationListItem, type Page, type Pillar } from "@/lib/api";
import { cn, DATA_DEPTH, psiSpan, span, years } from "@/lib/format";

const FILTER_KEYS = [
  "q", "fuel_state", "safety_function", "data_depth", "facility", "fuel", "oxygen_pct_min", "has_flow",
  "has_test_runs", "is_seed", "year_min", "year_max", "project",
] as const;

const FUEL_STATES = [
  { value: "gas", label: "Gas" },
  { value: "liquid", label: "Liquid" },
  { value: "solid", label: "Solid" },
];

function ConditionMetrics({ item }: { item: InvestigationListItem }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <Metric label="Oxygen" value={span(item.oxygen_pct_min, item.oxygen_pct_max)} unit="%" />
      <Metric
        label="Pressure"
        value={span(item.pressure_kpa_min, item.pressure_kpa_max)}
        unit="kPa"
        note={`${psiSpan(item.pressure_kpa_min, item.pressure_kpa_max)} psi`}
      />
      <Metric label="Flow" value={span(item.flow_speed_cm_s_min, item.flow_speed_cm_s_max)} unit="cm/s" />
    </div>
  );
}

function InvestigationCard({ item }: { item: InvestigationListItem }) {
  return (
    <Card className="flex flex-col gap-3 transition-colors hover:border-accent/60" data-testid="investigation-card">
      <div>
        <div className="flex items-center justify-between gap-2">
          <span className="num text-xs text-muted">{item.psi_id}</span>
          <span className="num text-xs text-muted">{years(item.start_date, item.end_date) ?? "Dates not recorded"}</span>
        </div>
        <h2 className="mt-1 text-lg font-semibold leading-snug">
          <Link to={`/investigations/${item.psi_id}`} className="hover:text-accent">
            {item.display_name}
          </Link>
        </h2>
        {item.acronym && <p className="line-clamp-2 text-sm text-muted">{item.title}</p>}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {item.safety_pillars.map((pillar) => (
          <PillarBadge key={pillar} pillar={pillar} />
        ))}
        {item.fuel_state && <Badge>{item.fuel_state} fuel</Badge>}
        <DepthBadge depth={item.data_depth} />
        {item.test_run_count > 0 && (
          <Badge>
            <span className="num">{item.test_run_count}</span> test runs
          </Badge>
        )}
      </div>
      <ConditionMetrics item={item} />
      <p className="line-clamp-3 text-sm text-muted">{item.objectives || "The PSI record has no objective text."}</p>
    </Card>
  );
}

function InvestigationTable({ items }: { items: InvestigationListItem[] }) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const columns = useMemo<ColumnDef<InvestigationListItem>[]>(
    () => [
      { header: "PSI", accessorFn: (row) => Number(row.psi_id.slice(4)), id: "psi", cell: ({ row }) => <span className="num">{row.original.psi_id}</span> },
      {
        header: "Investigation",
        accessorKey: "display_name",
        cell: ({ row }) => (
          <Link to={`/investigations/${row.original.psi_id}`} className="font-medium hover:text-accent">
            {row.original.display_name}
          </Link>
        ),
      },
      { header: "Fuel state", accessorKey: "fuel_state", cell: ({ getValue }) => (getValue() as string) || <span className="text-muted">—</span> },
      {
        header: "Safety function",
        accessorFn: (row) => row.safety_pillars.join(", "),
        id: "pillars",
        cell: ({ row }) => row.original.safety_pillars.map((p) => PILLARS[p].label).join(", ") || <span className="text-muted">—</span>,
      },
      { header: "Oxygen, %", accessorFn: (row) => row.oxygen_pct_max ?? -1, id: "oxygen", cell: ({ row }) => <span className="num">{span(row.original.oxygen_pct_min, row.original.oxygen_pct_max) ?? "—"}</span> },
      { header: "Pressure, kPa", accessorFn: (row) => row.pressure_kpa_max ?? -1, id: "pressure", cell: ({ row }) => <span className="num">{span(row.original.pressure_kpa_min, row.original.pressure_kpa_max) ?? "—"}</span> },
      { header: "Flow, cm/s", accessorFn: (row) => row.flow_speed_cm_s_max ?? -1, id: "flow", cell: ({ row }) => <span className="num">{span(row.original.flow_speed_cm_s_min, row.original.flow_speed_cm_s_max) ?? "—"}</span> },
      { header: "Test runs", accessorKey: "test_run_count", cell: ({ getValue }) => <span className="num">{getValue() as number}</span> },
      { header: "Data depth", accessorKey: "data_depth", cell: ({ getValue }) => DATA_DEPTH[getValue() as string]?.label ?? <span className="text-muted">—</span> },
    ],
    [],
  );
  const table = useReactTable({ data: items, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Investigations. A dash means the value is not recorded. Column headers sort the table.</caption>
        <thead className="border-b border-line text-xs text-muted">
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                return (
                  <th key={header.id} scope="col" aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"} className="whitespace-nowrap px-4 py-3 font-medium">
                    <button type="button" onClick={header.column.getToggleSortingHandler()} className="inline-flex items-center gap-1 hover:text-text">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {sorted === "asc" && <ArrowUp className="h-3 w-3" aria-hidden />}
                      {sorted === "desc" && <ArrowDown className="h-3 w-3" aria-hidden />}
                    </button>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-b border-line/60 last:border-0 hover:bg-surface-2/60">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-2.5">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export default function Investigations() {
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "table" ? "table" : "cards";
  const filters = Object.fromEntries(FILTER_KEYS.map((key) => [key, params.get(key) ?? ""]));
  const active = FILTER_KEYS.filter((key) => filters[key]);

  const set = (key: string, value: string | null) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  const toggleInList = (key: string, value: string) => {
    const list = filters[key] ? filters[key].split(",") : [];
    set(key, (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]).join(",") || null);
  };

  const query = useQuery({
    queryKey: ["investigations", filters],
    queryFn: () => api<Page<InvestigationListItem>>("/investigations/", { ...filters, page_size: 200 }),
    placeholderData: (previous) => previous,
  });
  const facilities = useQuery({ queryKey: ["facilities"], queryFn: () => api<Page<Facility>>("/facilities/", { page_size: 200 }) });
  const input = "rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm";

  return (
    <>
      <PageHeader
        title="Investigations"
        lead="Combustion Science investigations in NASA's PSI repository. Every card links back to its PSI record."
        actions={
          <div role="group" aria-label="View" className="flex rounded-lg border border-line p-0.5">
            {[
              { id: "cards", label: "Cards", icon: LayoutGrid },
              { id: "table", label: "Table", icon: Table2 },
            ].map(({ id, label, icon: Icon }) => (
              <button key={id} type="button" aria-pressed={view === id} onClick={() => set("view", id === "table" ? "table" : null)} className={cn("inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm", view === id ? "bg-accent/15 text-text" : "text-muted hover:text-text")}>
                <Icon className="h-4 w-4" aria-hidden />
                {label}
              </button>
            ))}
          </div>
        }
      />
      <Card className="no-print mb-5 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-[14rem] flex-1 flex-col gap-1 text-xs text-muted">
            Search this list
            <input value={filters.q} onChange={(e) => set("q", e.target.value)} placeholder="Acronym, title or text" className={input} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Facility
            <select value={filters.facility} onChange={(e) => set("facility", e.target.value)} className={input}>
              <option value="">Any facility</option>
              {facilities.data?.results.map((facility) => (
                <option key={facility.id} value={facility.name}>
                  {facility.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Fuel in test runs
            <input value={filters.fuel} onChange={(e) => set("fuel", e.target.value)} placeholder="for example heptane" className={cn(input, "w-40")} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Oxygen reaches at least, %
            <input type="number" min={0} max={100} value={filters.oxygen_pct_min} onChange={(e) => set("oxygen_pct_min", e.target.value)} className={cn(input, "num w-28")} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Active from year
            <input type="number" value={filters.year_min} onChange={(e) => set("year_min", e.target.value)} className={cn(input, "num w-24")} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            to year
            <input type="number" value={filters.year_max} onChange={(e) => set("year_max", e.target.value)} className={cn(input, "num w-24")} />
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div role="group" aria-label="Safety function" className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted">Safety function</span>
            {(Object.keys(PILLARS) as Pillar[]).map((pillar) => (
              <Chip key={pillar} active={filters.safety_function === pillar} onClick={() => set("safety_function", filters.safety_function === pillar ? null : pillar)}>
                {PILLARS[pillar].label}
              </Chip>
            ))}
          </div>
          <div role="group" aria-label="Fuel state" className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted">Fuel state</span>
            {FUEL_STATES.map(({ value, label }) => (
              <Chip key={value} active={filters.fuel_state.split(",").includes(value)} onClick={() => toggleInList("fuel_state", value)}>
                {label}
              </Chip>
            ))}
          </div>
          <div role="group" aria-label="Data depth" className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted">Data depth</span>
            {Object.entries(DATA_DEPTH).map(([value, { label }]) => (
              <Chip key={value} active={filters.data_depth.split(",").includes(value)} onClick={() => toggleInList("data_depth", value)}>
                {label}
              </Chip>
            ))}
          </div>
          <div role="group" aria-label="More filters" className="flex flex-wrap items-center gap-1.5">
            <Chip active={filters.has_flow === "true"} onClick={() => set("has_flow", filters.has_flow ? null : "true")}>Flow speed recorded</Chip>
            <Chip active={filters.has_test_runs === "true"} onClick={() => set("has_test_runs", filters.has_test_runs ? null : "true")}>Has test runs</Chip>
            <Chip active={filters.is_seed === "true"} onClick={() => set("is_seed", filters.is_seed ? null : "true")}>Named in the challenge brief</Chip>
            {filters.project && <Chip active onClick={() => set("project", null)}>Project: {filters.project}</Chip>}
          </div>
        </div>
      </Card>

      <div className="mb-3 flex items-center justify-between gap-3 text-sm text-muted" aria-live="polite">
        <span data-testid="result-count">
          {query.data ? `${query.data.count} ${query.data.count === 1 ? "investigation" : "investigations"}` : "Loading…"}
          {active.length > 0 && `, ${active.length} ${active.length === 1 ? "filter" : "filters"} applied`}
        </span>
        {active.length > 0 && (
          <Button variant="ghost" onClick={() => setParams(view === "table" ? { view: "table" } : {}, { replace: true })}>
            Clear filters
          </Button>
        )}
      </div>

      {query.isError && <ErrorState error={query.error} />}
      {query.isPending && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      )}
      {query.data?.count === 0 && (
        <EmptyState title="No investigation matches these filters">
          Fuel state and safety function are filled in by the AI extraction step; a record without them is not matched by those filters. Remove a filter or clear them all.
        </EmptyState>
      )}
      {query.data && query.data.count > 0 &&
        (view === "table" ? (
          <InvestigationTable items={query.data.results} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {query.data.results.map((item) => (
              <InvestigationCard key={item.psi_id} item={item} />
            ))}
          </div>
        ))}
    </>
  );
}
