export type LoginButtonAction = "open-login" | "start-demo" | "ignore";

export function resolveLoginButtonPress({
  now,
  lastPressAt,
  demoActive,
  doubleClickMs = 350,
}: {
  now: number;
  lastPressAt: number;
  demoActive: boolean;
  doubleClickMs?: number;
}): { action: LoginButtonAction; nextLastPressAt: number } {
  if (demoActive) {
    return { action: "ignore", nextLastPressAt: lastPressAt || 0 };
  }
  if (lastPressAt > 0 && now - lastPressAt <= doubleClickMs) {
    return { action: "start-demo", nextLastPressAt: 0 };
  }
  return { action: "open-login", nextLastPressAt: now };
}
