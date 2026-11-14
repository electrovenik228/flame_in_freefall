import { describe, expect, it } from "vitest";

import { bytes, psiSpan, span, years } from "./format";

describe("format", () => {
  it("shows a span, a single value, or nothing", () => {
    expect(span(12, 34)).toBe("12–34");
    expect(span(21.5, 21.5)).toBe("21.5");
    expect(span(null, null)).toBeNull();
    expect(span(null, 30)).toBe("30");
  });
  it("converts kPa to psi", () => {
    expect(psiSpan(101.325, 101.325)).toBe("14.7");
    expect(psiSpan(null, null)).toBeNull();
  });
  it("formats years and sizes", () => {
    expect(years("2009-10-01", "2013-06-30")).toBe("2009–2013");
    expect(years(null, null)).toBeNull();
    expect(bytes(923_800_000_000)).toBe("924 GB");
  });
});
