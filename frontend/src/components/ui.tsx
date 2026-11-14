import { Bell, Droplets, ExternalLink, ShieldCheck, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import type { Pillar } from "@/lib/api";
import { cn, DATA_DEPTH } from "@/lib/format";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card border border-line bg-surface p-5", className)} {...props} />;
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{children}</h2>
      {aside}
    </div>
  );
}

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs text-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variant === "default" && "border border-line bg-surface-2 text-text hover:border-accent",
        variant === "primary" && "bg-accent text-bg hover:opacity-90",
        variant === "ghost" && "text-muted hover:bg-surface-2 hover:text-text",
        className,
      )}
      {...props}
    />
  );
}

/** Toggle chip. State is carried by aria-pressed and a check mark, not by colour alone. */
export function Chip({
  active,
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors",
        active ? "border-accent bg-accent/15 text-text" : "border-line bg-surface text-muted hover:text-text",
        className,
      )}
      {...props}
    >
      {active && <span aria-hidden>✓</span>}
      {children}
    </button>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-surface-2", className)} aria-hidden />;
}

export function ExternalA({ href, children, className }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cn("inline-flex items-center gap-1 text-accent underline-offset-2 hover:underline", className)}
    >
      {children}
      <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
    </a>
  );
}

export const PILLARS: Record<Pillar, { label: string; icon: LucideIcon; text: string; hint: string }> = {
  prevention: {
    label: "Prevention",
    icon: ShieldCheck,
    text: "text-prevention",
    hint: "Material flammability and ignition limits",
  },
  detection: { label: "Detection", icon: Bell, text: "text-detection", hint: "Smoke and early fire signatures" },
  suppression: { label: "Suppression", icon: Droplets, text: "text-suppression", hint: "Extinguishment and suppressants" },
};

export function PillarBadge({ pillar }: { pillar: Pillar }) {
  const { label, icon: Icon, text } = PILLARS[pillar];
  return (
    <Badge className={cn("border-current/30", text)} title={PILLARS[pillar].hint}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {label}
    </Badge>
  );
}

export function DepthBadge({ depth }: { depth: string }) {
  const info = DATA_DEPTH[depth];
  if (!info) return <Badge title="Data depth has not been determined for this record">Depth not determined</Badge>;
  return <Badge title={info.hint}>{info.label}</Badge>;
}

export function Metric({ label, value, unit, note }: { label: string; value: string | null; unit?: string; note?: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      {value === null ? (
        <div className="text-sm text-muted">Not recorded</div>
      ) : (
        <div className="num text-sm text-text">
          {value}
          {unit && <span className="ml-1 text-muted">{unit}</span>}
        </div>
      )}
      {note && value !== null && <div className="num text-xs text-muted">{note}</div>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Card className="border-dashed text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-xl text-sm text-muted">{children}</div>}
    </Card>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  return (
    <Card role="alert" className="border-danger/50">
      <p className="font-medium text-danger">Something went wrong</p>
      <p className="mt-1 text-sm text-muted">{error instanceof Error ? error.message : "The request failed."}</p>
    </Card>
  );
}

export function PageHeader({ title, lead, actions }: { title: string; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {lead && <p className="mt-1 text-muted">{lead}</p>}
      </div>
      {actions && <div className="no-print flex items-center gap-2">{actions}</div>}
    </header>
  );
}
