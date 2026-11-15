import { AlertTriangle, CheckCircle2, Send } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { AiLabel, CitedText } from "@/components/Cited";
import { Button, Card, PageHeader } from "@/components/ui";
import { api, apiUrl, type Citation, type Segment } from "@/lib/api";
import { cn } from "@/lib/format";

interface Verification {
  has_citation: boolean;
  unmatched_numbers: string[];
  verified: boolean | null;
}

interface ChatMessage {
  role: "user" | "assistant";
  segments: Segment[];
  citations: Citation[];
  status?: string;
  notice?: { text: string; kind: string };
  model?: string;
  generatedAt?: string;
  verification?: Verification | null;
}

const SUGGESTIONS = [
  "Which investigations matter most for a lunar habitat with 30% oxygen, and why?",
  "How do BASS-II and Saffire differ in sample size and flow?",
  "What has been tested on fire suppression in microgravity?",
  "Which records give test-by-test oxygen and pressure data for validating a model?",
  "What did the SAME experiments learn about smoke particles in microgravity?",
];
const STORAGE_KEY = "assistant-conversation";
const JSON_HEADERS = { "Content-Type": "application/json" };
const FAILED = { text: "The assistant cannot be reached right now. Stored summaries, rankings and charts keep working.", kind: "unavailable" };

function VerificationMark({ verification }: { verification?: Verification | null }) {
  if (!verification || verification.verified === null) return null;
  if (verification.verified) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-detection" data-testid="verified">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        Numbers checked against the cited records
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-warm" data-testid="flagged">
      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
      {verification.unmatched_numbers.length > 0
        ? `Not found in the cited records: ${verification.unmatched_numbers.join(", ")}. Check these against PSI.`
        : "This answer carries no citation. Treat it as unverified."}
    </span>
  );
}

export default function Assistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const conversation = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  // History is shown for this browser session only (section 8.1).
  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    api<{ messages: { role: "user" | "assistant"; segments: Segment[]; citations: Citation[]; model: string; generated_at: string; verification: Verification | null }[] }>(`/assistant/conversations/${stored}/`)
      .then((data) => {
        conversation.current = stored;
        setMessages(data.messages.map((m) => ({ role: m.role, segments: m.segments, citations: m.citations, model: m.model, generatedAt: m.generated_at, verification: m.verification })));
      })
      .catch(() => sessionStorage.removeItem(STORAGE_KEY));
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const patchLast = (change: (message: ChatMessage) => ChatMessage) =>
    setMessages((current) => current.map((message, index) => (index === current.length - 1 ? change(message) : message)));

  const handle = (event: string, data: Record<string, unknown>) => {
    if (event === "status") patchLast((m) => ({ ...m, status: data.text as string }));
    else if (event === "block") patchLast((m) => ({ ...m, status: undefined, segments: [...m.segments, { text: "", citations: [] }] }));
    else if (event === "delta") patchLast((m) => ({ ...m, segments: m.segments.map((s, i) => (i === data.index ? { ...s, text: s.text + (data.text as string) } : s)) }));
    else if (event === "citation") {
      const citation = data.citation as Citation;
      patchLast((m) => ({
        ...m,
        citations: m.citations.some((c) => c.n === citation.n) ? m.citations : [...m.citations, citation],
        segments: m.segments.map((s, i) => (i === data.index && !s.citations.includes(citation.n) ? { ...s, citations: [...s.citations, citation.n] } : s)),
      }));
    } else if (event === "reset") patchLast((m) => ({ ...m, segments: [], citations: [] }));
    else if (event === "notice") patchLast((m) => ({ ...m, status: undefined, notice: data as { text: string; kind: string } }));
    else if (event === "done") patchLast((m) => ({ ...m, status: undefined, model: data.model as string, generatedAt: data.generated_at as string, verification: data.verification as Verification }));
  };

  const send = async (question: string) => {
    if (!question.trim() || busy) return;
    setBusy(true);
    setText("");
    setMessages((current) => [
      ...current,
      { role: "user", segments: [{ text: question, citations: [] }], citations: [] },
      { role: "assistant", segments: [], citations: [], status: "Sending…" },
    ]);
    try {
      if (!conversation.current) {
        const created = await api<{ id: string }>("/assistant/conversations/", undefined, { method: "POST", headers: JSON_HEADERS, body: "{}" });
        conversation.current = created.id;
        sessionStorage.setItem(STORAGE_KEY, created.id);
      }
      const response = await fetch(apiUrl(`/assistant/conversations/${conversation.current}/messages/`), {
        method: "POST",
        headers: JSON_HEADERS,
        credentials: "same-origin",
        body: JSON.stringify({ content: question }),
      });
      if (!response.ok || !response.body) throw new Error(`Request failed (${response.status})`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const event = /^event: (.+)$/m.exec(chunk)?.[1];
          const data = /^data: (.+)$/m.exec(chunk)?.[1];
          if (event && data) handle(event, JSON.parse(data));
        }
      }
    } catch {
      patchLast((m) => ({ ...m, status: undefined, notice: FAILED }));
    } finally {
      patchLast((m) => ({ ...m, status: undefined }));
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void send(text);
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col">
      <PageHeader
        title="Research assistant"
        lead="Ask about the investigations in the catalogue. Answers are written by AI from PSI records only, with numbered sources you can open."
      />
      {messages.length === 0 && (
        <Card className="mb-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Try a question</h2>
          <ul className="space-y-2">
            {SUGGESTIONS.map((suggestion) => (
              <li key={suggestion}>
                <button type="button" onClick={() => void send(suggestion)} className="w-full rounded-lg border border-line px-3 py-2 text-left text-sm hover:border-accent">
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <ol className="space-y-4" aria-live="polite" data-testid="chat">
        {messages.map((message, index) => (
          <li key={index} className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}>
            {message.role === "user" ? (
              <p className="max-w-[85%] rounded-card bg-accent/15 px-4 py-2.5">{message.segments[0]?.text}</p>
            ) : (
              <Card className="w-full" data-testid="answer">
                {message.status && <p className="animate-pulse text-sm text-muted" data-testid="status">{message.status}</p>}
                {message.segments.length > 0 && (
                  <p className="text-[0.95rem] leading-relaxed">
                    <CitedText segments={message.segments} citations={message.citations} />
                  </p>
                )}
                {message.notice && <p role="status" className="text-sm text-muted" data-testid="notice">{message.notice.text}</p>}
                {message.model && (
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3">
                    <AiLabel model={message.model} generatedAt={message.generatedAt} reviewStatus="unreviewed" />
                    <VerificationMark verification={message.verification} />
                  </div>
                )}
              </Card>
            )}
          </li>
        ))}
      </ol>
      <div ref={bottom} />
      <form onSubmit={submit} className="no-print sticky bottom-0 mt-4 flex gap-2 bg-bg py-3">
        <label className="sr-only" htmlFor="question">Your question</label>
        <input
          id="question"
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={2000}
          placeholder="Ask about an investigation, a fuel, an environment…"
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2.5"
        />
        <Button variant="primary" type="submit" disabled={busy || !text.trim()}>
          <Send className="h-4 w-4" aria-hidden />
          Ask
        </Button>
      </form>
      <p className="text-xs text-muted">
        The assistant answers only from the catalogue and declines other topics. Conversations are kept for 30 days under an anonymous session ID, without your IP address, for quality review. It is a research aid, not a safety authority.
      </p>
    </div>
  );
}
