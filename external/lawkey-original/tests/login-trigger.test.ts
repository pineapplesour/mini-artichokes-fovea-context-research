import { describe, expect, it } from "vitest";

import { resolveLoginButtonPress } from "../lib/login-trigger";

describe("login button trigger", () => {
  it("opens the login dialog on the first click", () => {
    expect(resolveLoginButtonPress({ now: 1_000, lastPressAt: 0, demoActive: false })).toEqual({
      action: "open-login",
      nextLastPressAt: 1_000,
    });
  });

  it("starts the demo only on a fast second click", () => {
    expect(resolveLoginButtonPress({ now: 1_250, lastPressAt: 1_000, demoActive: false })).toEqual({
      action: "start-demo",
      nextLastPressAt: 0,
    });
  });

  it("does not start the demo when the second click is too late", () => {
    expect(resolveLoginButtonPress({ now: 1_500, lastPressAt: 1_000, demoActive: false })).toEqual({
      action: "open-login",
      nextLastPressAt: 1_500,
    });
  });
});
