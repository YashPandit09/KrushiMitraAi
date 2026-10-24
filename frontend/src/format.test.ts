import { describe, expect, it } from "vitest";
import { classFor, DIVERGING, SEQUENTIAL } from "./colors";
import { barPath, linear, niceStep, ticks } from "./components/scale";
import { driverValue, paddyQuintalPerAcre, signed, signedPct, tHa } from "./format";

describe("format", () => {
  it("formats yields and signed percentages with a true minus sign", () => {
    expect(tHa(2.345)).toBe("2.35 t/ha");
    expect(tHa(null)).toBe("–");
    expect(signedPct(4.06)).toBe("+4%");
    expect(signedPct(-12.4)).toBe("−12%");
    expect(signedPct(0.2)).toBe("±0%");
    expect(signed(-0.123, 2)).toBe("−0.12");
  });

  it("describes drivers by unit", () => {
    expect(driverValue(-0.32, "pct")).toBe("−32%");
    expect(driverValue(1.26, "degC")).toBe("+1.3 °C");
    expect(driverValue(0, "kt")).toBe("none");
    expect(driverValue(115, "kt")).toBe("115 knots");
  });

  it("converts milled rice t/ha to approximate paddy quintals per acre", () => {
    // 2 t/ha rice -> 2.985 t/ha paddy -> 29.85 q/ha -> ~12.1 q/acre
    expect(paddyQuintalPerAcre(2)).toBeCloseTo(12.08, 1);
  });
});

describe("colour classes", () => {
  it("covers the whole real line exactly once (diverging)", () => {
    for (const v of [-80, -20, -19.9, -10, -3.01, -3, 0, 3, 3.01, 9.99, 10, 20, 150]) {
      expect(DIVERGING.filter((c) => c.test(v))).toHaveLength(1);
    }
    expect(classFor(DIVERGING, 0)?.token).toBe("--div-0");
    expect(classFor(DIVERGING, -25)?.token).toBe("--div-n3");
  });

  it("covers the whole range exactly once (sequential)", () => {
    for (const v of [0, 1.49, 1.5, 2, 2.5, 2.99, 3, 9]) {
      expect(SEQUENTIAL.filter((c) => c.test(v))).toHaveLength(1);
    }
    expect(classFor(SEQUENTIAL, null)).toBeUndefined();
  });
});

describe("scales", () => {
  it("maps and inverts linearly", () => {
    const s = linear([0, 10], [100, 200]);
    expect(s(5)).toBe(150);
    expect(s.invert(175)).toBe(7.5);
  });

  it("produces nice ticks that cover the data", () => {
    expect(niceStep(3.1, 5)).toBe(1);
    const t = ticks(0, 3.1, 5);
    expect(t.values[0]).toBe(0);
    expect(t.max).toBeGreaterThanOrEqual(3.1);
  });

  it("draws bars with a rounded data end only", () => {
    expect(barPath(0, 0, 10, 20, 4, "top")).toMatch(/^M0,20V4Q0,0 4,0H6Q10,0 10,4V20Z$/);
  });
});
