import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Citation, Segment } from "@/lib/api";
import { dateTime } from "@/lib/format";

import { ExternalA } from "./ui";

/** Small numbered marker that opens the source passage and the PSI link (section 10.3). */
export function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <span ref={ref} className="relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={`Source ${citation.n}: ${citation.psi_id}, ${citation.document_title}`}
        className="num mx-0.5 inline-flex h-[1.15rem] min-w-[1.15rem] items-center justify-center rounded border border-accent/50 bg-accent/10 px-1 text-[0.68rem] leading-none text-accent hover:bg-accent/25"
      >
        {citation.n}
      </button>
      {open && (
        <span role="dialog" aria-label={`Source ${citation.n}`} className="absolute left-0 top-6 z-30 block w-80 max-w-[80vw] rounded-card border border-line bg-surface p-3 text-left text-sm font-normal shadow-xl">
          <span className="num block text-xs text-muted">
            {citation.psi_id} · {citation.document_title}
          </span>
          <span className="my-2 block max-h-48 overflow-auto border-l-2 border-accent/60 pl-2 text-text">“{citation.cited_text}”</span>
          <ExternalA href={citation.psi_url}>View on PSI</ExternalA>
        </span>
      )}
    </span>
  );
}

export function CitedText({ segments, citations }: { segments: Segment[]; citations: Citation[] }) {
  const byNumber = new Map(citations.map((citation) => [citation.n, citation]));
  return (
    <span className="whitespace-pre-wrap">
      {segments.map((segment, index) => (
        <span key={index}>
          {segment.text}
          {segment.citations.map((n) => {
            const citation = byNumber.get(n);
            return citation ? <CitationChip key={n} citation={citation} /> : null;
          })}
        </span>
      ))}
    </span>
  );
}

/** Every AI item carries its mark, model, date and review state (section 7.5). */
export function AiLabel({ model, generatedAt, reviewStatus }: { model: string; generatedAt?: string; reviewStatus?: string }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted">
      <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5">
        <Sparkles className="h-3 w-3" aria-hidden />
        AI-generated
      </span>
      <span className="num">{model}</span>
      {generatedAt && <span>{dateTime(generatedAt)}</span>}
      {reviewStatus && <span>{reviewStatus === "approved" ? "Reviewed" : "Not yet reviewed by an expert"}</span>}
    </span>
  );
}
