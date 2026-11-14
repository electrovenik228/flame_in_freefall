import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, Printer } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { AiLabel, CitedText } from "@/components/Cited";
import { Badge, Button, Card, Chip, DepthBadge, EmptyState, ErrorState, ExternalA, Metric, PillarBadge, SectionTitle, Skeleton } from "@/components/ui";
import { api, apiUrl, ApiError, type InvestigationDetail as Detail, type Page, type TestRun, type VariableEntry } from "@/lib/api";
import { bytes, CONDITIONS_SOURCE, dateTime, fmt, psiSpan, span, years } from "@/lib/format";

function TextSection({ title, text }: { title: string; text: string }) {
  if (!text) return null;
  return (
    <section>
      <SectionTitle>{title}</SectionTitle>
      <p className="max-w-prose whitespace-pre-line text-[0.95rem] leading-relaxed">{text}</p>
    </section>
  );
}

function VariableList({ title, items, empty }: { title: string; items: VariableEntry[]; empty: string }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {items.map((item) => (
            <li key={item.field} className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span>{item.label}</span>
              <span className="num text-muted">
                {item.min != null && item.max != null
                  ? `${span(item.min, item.max)} ${item.unit ?? ""}`
                  : item.values
                    ? item.values.join(", ")
                    : `${item.distinct_values} values`}
                {item.recorded_runs != null && <span className="ml-2 text-xs">in {item.recorded_runs} runs</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Summary({ data }: { data: Detail }) {
  const [level, setLevel] = useState<"plain" | "expert">("plain");
  if (!data.summary) {
    return (
      <Card className="border-dashed">
        <SectionTitle>Summary</SectionTitle>
        <p className="text-sm text-muted">
          No AI summary is stored for this record yet. The sections below show the PSI record text as NASA published it.
        </p>
      </Card>
    );
  }
  const { content, citations, model, generated_at, review_status } = data.summary;
  return (
    <Card data-testid="ai-summary">
      <SectionTitle
        aside={
          <div role="group" aria-label="Reading level" className="no-print flex gap-1.5">
            <Chip active={level === "plain"} onClick={() => setLevel("plain")}>Plain</Chip>
            <Chip active={level === "expert"} onClick={() => setLevel("expert")}>Expert</Chip>
          </div>
        }
      >
        Summary
      </SectionTitle>
      <p className="max-w-prose text-[0.95rem] leading-relaxed">
        <CitedText segments={content[level]} citations={citations} />
      </p>
      <div className="mt-4 border-t border-line pt-3">
        <AiLabel model={model} generatedAt={generated_at} reviewStatus={review_status} />
      </div>
    </Card>
  );
}

function TestRuns({ psiId, count }: { psiId: string; count: number }) {
  const runs = useQuery({
    queryKey: ["test-runs", psiId],
    queryFn: () => api<Page<TestRun>>(`/investigations/${psiId}/test-runs/`, { page_size: 15 }),
  });
  const cell = (value: ReactNode) => value ?? <span className="text-muted">—</span>;
  return (
    <section>
      <SectionTitle
        aside={
          <a href={apiUrl("/test-runs/export/", { investigation: psiId })} className="no-print inline-flex items-center gap-1 text-sm text-accent hover:underline">
            <Download className="h-3.5 w-3.5" aria-hidden />
            Export all {count} rows as CSV
          </a>
        }
      >
        Test runs
      </SectionTitle>
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">First 15 test runs. A dash means the value is not in the PSI table.</caption>
          <thead className="border-b border-line text-xs text-muted">
            <tr>
              {["Test", "Fuel", "Oxygen, %", "Pressure, kPa", "Flow, cm/s", "Outcome", "Source row"].map((heading) => (
                <th key={heading} scope="col" className="whitespace-nowrap px-4 py-2.5 font-medium">{heading}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.data?.results.map((run) => (
              <tr key={run.id} className="border-b border-line/60 last:border-0">
                <td className="num px-4 py-2">{run.test_label || "—"}</td>
                <td className="px-4 py-2">{cell(run.fuel || null)}</td>
                <td className="num px-4 py-2">{cell(run.oxygen_pct != null ? fmt(run.oxygen_pct) : null)}</td>
                <td className="num px-4 py-2">{cell(run.pressure_kpa != null ? fmt(run.pressure_kpa) : null)}</td>
                <td className="num px-4 py-2">{cell(run.flow_speed_cm_s != null ? fmt(run.flow_speed_cm_s) : null)}</td>
                <td className="px-4 py-2">{cell(run.extinction_mode || (run.ignited === false ? "Did not ignite" : null))}</td>
                <td className="num px-4 py-2 text-muted" title={run.source_file}>{run.source_row}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {count > 15 && <p className="mt-2 text-xs text-muted">Showing the first 15 of {count} runs. The export holds every row with its PSI file and row number.</p>}
    </section>
  );
}

export default function InvestigationDetail() {
  const { psiId = "" } = useParams();
  const { data, error, isPending } = useQuery({
    queryKey: ["investigation", psiId],
    queryFn: () => api<Detail>(`/investigations/${psiId}/`),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  if (isPending) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState title={`${psiId} is not in the catalogue`}>
        The catalogue holds the Combustion Science records of PSI. <Link to="/investigations" className="text-accent hover:underline">Browse all investigations</Link>
      </EmptyState>
    );
  }
  if (error) return <ErrorState error={error} />;

  const hasRuns = data.variables.test_run_count > 0;
  const hasRanges = data.oxygen_pct_max != null || data.pressure_kpa_max != null || data.flow_speed_cm_s_max != null;
  return (
    <article className="space-y-6">
      <header>
        <Link to="/investigations" className="no-print mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-text">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Investigations
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="num flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
              <span data-testid="psi-id">{data.psi_id}</span>
              {data.doi && <ExternalA href={`https://doi.org/${data.doi}`}>DOI {data.doi}</ExternalA>}
              <span>{years(data.start_date, data.end_date) ?? "Dates not recorded"}</span>
            </div>
            <h1 className="mt-1 text-2xl font-semibold">{data.display_name}</h1>
            {data.acronym && <p className="text-muted">{data.title}</p>}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {data.safety_pillars.map((pillar) => <PillarBadge key={pillar} pillar={pillar} />)}
              {data.fuel_state && <Badge>{data.fuel_state} fuel</Badge>}
              <DepthBadge depth={data.data_depth} />
              {data.project && <Badge>{data.project}</Badge>}
              {data.project_type && <Badge>{data.project_type}</Badge>}
            </div>
          </div>
          <div className="no-print flex items-center gap-2">
            <Button onClick={() => window.print()}><Printer className="h-4 w-4" aria-hidden />Print report</Button>
            <a href={data.psi_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90">
              View on PSI
            </a>
          </div>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Summary data={data} />
          <TextSection title="Objectives" text={data.objectives} />
          <TextSection title="Approach" text={data.approach} />
          <TextSection title="Hypothesis" text={data.hypothesis} />
          <TextSection title="Benefits and research impact" text={data.benefits} />
        </div>

        <div className="space-y-6">
          <Card>
            <SectionTitle>Test conditions</SectionTitle>
            {hasRanges ? (
              <div className="grid grid-cols-2 gap-4">
                <Metric label="Oxygen" value={span(data.oxygen_pct_min, data.oxygen_pct_max)} unit="% by volume" />
                <Metric label="Pressure" value={span(data.pressure_kpa_min, data.pressure_kpa_max)} unit="kPa" note={`${psiSpan(data.pressure_kpa_min, data.pressure_kpa_max)} psi`} />
                <Metric label="Flow speed" value={span(data.flow_speed_cm_s_min, data.flow_speed_cm_s_max)} unit="cm/s" />
                <Metric label="Test runs" value={hasRuns ? String(data.variables.test_run_count) : null} />
              </div>
            ) : (
              <p className="text-sm text-muted">No oxygen, pressure or flow range is stored for this record.</p>
            )}
            <p className="mt-3 text-xs text-muted">Source of ranges: {CONDITIONS_SOURCE[data.conditions_source]}.</p>
          </Card>

          {hasRuns ? (
            <Card className="space-y-4">
              <SectionTitle>Variables</SectionTitle>
              <VariableList title="Varied between tests" items={data.variables.varied} empty="Nothing varied in the recorded columns." />
              <VariableList title="Held constant" items={data.variables.constant} empty="No recorded column was constant." />
              {data.variables.not_recorded.length > 0 && (
                <p className="text-xs text-muted">Not in the PSI table: {data.variables.not_recorded.map((item) => item.label.toLowerCase()).join(", ")}.</p>
              )}
            </Card>
          ) : (
            <Card className="border-warm/40" data-testid="no-per-test-notice">
              <SectionTitle>No per-test data</SectionTitle>
              <p className="text-sm text-muted">
                This record has no test-by-test table in the catalogue, so there are no charts or varied and constant variables to show.
                {data.file_count > 0 && " Its experiment table is kept as a source document and is linked from PSI."}
              </p>
            </Card>
          )}

          <Card>
            <SectionTitle>Hardware</SectionTitle>
            {data.facilities.length > 0 && (
              <ul className="mb-2 space-y-1 text-sm">
                {data.facilities.map((facility) => (
                  <li key={facility.id}>
                    <Link to={`/investigations?facility=${encodeURIComponent(facility.name)}`} className="hover:text-accent">{facility.name}</Link>
                    <span className="ml-2 text-xs text-muted">{facility.type}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-sm text-muted">{data.hardware_text ? `As written in PSI: ${data.hardware_text}` : "The PSI record names no hardware."}</p>
            {data.hardware_links.map((link) => (
              <ExternalA key={link} href={link} className="mt-1 block truncate text-sm">{link.replace(/^https?:\/\//, "")}</ExternalA>
            ))}
            {data.instruments.length > 0 && (
              <>
                <h3 className="mb-1 mt-4 text-sm font-medium">Sensors</h3>
                <ul className="space-y-1 text-sm">
                  {data.instruments.map((instrument) => (
                    <li key={instrument.id}>{instrument.name}<span className="ml-2 text-xs text-muted">{instrument.measurement_type}</span></li>
                  ))}
                </ul>
              </>
            )}
          </Card>

          <Card>
            <SectionTitle>Record</SectionTitle>
            <dl className="space-y-1.5 text-sm">
              {([
                ["PSI version", data.psi_version != null ? String(data.psi_version) : null],
                ["Raw data in PSI", bytes(data.total_file_size)],
                ["Flight program", data.flight_program || null],
                ["Retrieved", data.retrieved_at ? dateTime(data.retrieved_at) : null],
                ["Licence", data.license_name || null],
              ] as [string, string | null][]).filter(([, value]) => value).map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3"><dt className="text-muted">{label}</dt><dd className="num text-right">{value}</dd></div>
              ))}
            </dl>
            {data.contacts.length > 0 && (
              <p className="mt-3 text-xs text-muted">
                {data.contacts.slice(0, 4).map((contact) => `${contact.name} (${contact.roles[0] ?? "contact"})`).join("; ")}
                {data.contacts.length > 4 && ` and ${data.contacts.length - 4} more`}
              </p>
            )}
            {data.related.length > 0 && (
              <>
                <h3 className="mb-1 mt-4 text-sm font-medium">Related records</h3>
                <ul className="space-y-1 text-sm">
                  {data.related.map((item) => (
                    <li key={item.psi_id}><Link to={`/investigations/${item.psi_id}`} className="hover:text-accent"><span className="num mr-2 text-xs text-muted">{item.psi_id}</span>{item.display_name}</Link></li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        </div>
      </div>

      {hasRuns && <TestRuns psiId={data.psi_id} count={data.variables.test_run_count} />}

      <section id="publications">
        <SectionTitle>Publications ({data.publications.length})</SectionTitle>
        {data.publications.length === 0 ? (
          <p className="text-sm text-muted">The PSI record lists no publications.</p>
        ) : (
          <Card>
            <ol className="max-h-96 space-y-3 overflow-auto text-sm">
              {data.publications.map((publication) => (
                <li key={publication.id}>
                  {publication.url ? <ExternalA href={publication.url}>{publication.title}</ExternalA> : publication.title}
                  {publication.authors && <span className="block text-xs text-muted">{publication.authors}</span>}
                </li>
              ))}
            </ol>
          </Card>
        )}
      </section>
    </article>
  );
}
