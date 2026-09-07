import { describe, expect, it } from "vitest";

import { detectConstrainedMode } from "../lib/performance-mode";

describe("detectConstrainedMode", () => {
  it("returns true for <=1 Mbps links", () => {
    expect(detectConstrainedMode({ downlinkMbps: 1 })).toBe(true);
  });

  it("returns true for low-memory/low-core devices", () => {
    expect(detectConstrainedMode({ deviceMemoryGb: 4, hardwareConcurrency: 4 })).toBe(true);
  });

  it("returns false for comfortable devices", () => {
    expect(detectConstrainedMode({ downlinkMbps: 30, deviceMemoryGb: 8, hardwareConcurrency: 8 })).toBe(false);
  });
});
