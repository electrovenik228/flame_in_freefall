import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const KPA_TO_PSI = 0.1450377;

export function fmt(value: number, digits = 1): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(digits);
}

/** "12–34" for a span, "21.5" for a single value, "≤ 40" for a one-sided bound, null when nothing is recorded. */
export function span(min: number | null | undefined, max: number | null | undefined, digits = 1): string | null {
  if (min == null && max == null) return null;
  if (min == null) return `≤ ${fmt(max!, digits)}`;
  if (max == null) return `≥ ${fmt(min, digits)}`;
  return fmt(min, digits) === fmt(max, digits) ? fmt(min, digits) : `${fmt(min, digits)}–${fmt(max, digits)}`;
}

export function psiSpan(min: number | null | undefined, max: number | null | undefined): string | null {
  return span(min == null ? min : min * KPA_TO_PSI, max == null ? max : max * KPA_TO_PSI);
}

export function kpaToPsi(value: number): number {
  return value * KPA_TO_PSI;
}

export function year(date: string | null): string | null {
  return date ? date.slice(0, 4) : null;
}

export function years(start: string | null, end: string | null): string | null {
  const a = year(start);
  const b = year(end);
  if (!a && !b) return null;
  if (a && b) return a === b ? a : `${a}–${b}`;
  return a ? `${a}–` : `–${b}`;
}

export function bytes(size: number | null): string | null {
  if (size == null) return null;
  const units = ["B", "kB", "MB", "GB", "TB"];
  let value = size;
  let index = 0;
  while (value >= 1000 && index < units.length - 1) {
    value /= 1000;
    index += 1;
  }
  return `${value.toFixed(value >= 100 || index === 0 ? 0 : 1)} ${units[index]}`;
}

export function dateTime(value: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export const DATA_DEPTH: Record<string, { label: string; hint: string }> = {
  per_test: { label: "Per-test data", hint: "The record publishes conditions for individual tests." },
  telemetry: { label: "Telemetry", hint: "The record holds time-series telemetry." },
  summary: { label: "Summary table", hint: "The record gives a test matrix or summary, not individual tests." },
  qualitative: { label: "Qualitative", hint: "The record is descriptive; there is no table of test conditions." },
};

export const CONDITIONS_SOURCE: Record<string, string> = {
  test_runs: "Computed from the record's test runs",
  record_text: "Read from the record text by AI, with a quoted source",
  not_available: "The record does not state test conditions",
  "": "Not determined yet",
};
