export type ConstrainedModeSignals = {
  saveData?: boolean | null;
  downlinkMbps?: number | null;
  effectiveType?: string | null;
  deviceMemoryGb?: number | null;
  hardwareConcurrency?: number | null;
};

const SLOW_EFFECTIVE_TYPES = new Set(["slow-2g", "2g", "3g"]);

export const detectConstrainedMode = ({
  saveData,
  downlinkMbps,
  effectiveType,
  deviceMemoryGb,
  hardwareConcurrency,
}: ConstrainedModeSignals) => {
  if (saveData) {
    return true;
  }

  if (typeof downlinkMbps === "number" && Number.isFinite(downlinkMbps) && downlinkMbps <= 1) {
    return true;
  }

  if (effectiveType && SLOW_EFFECTIVE_TYPES.has(effectiveType)) {
    return true;
  }

  if (typeof deviceMemoryGb === "number" && Number.isFinite(deviceMemoryGb) && deviceMemoryGb <= 4) {
    return true;
  }

  if (typeof hardwareConcurrency === "number" && Number.isFinite(hardwareConcurrency) && hardwareConcurrency <= 4) {
    return true;
  }

  return false;
};

export const isConstrainedClient = () => {
  if (typeof window === "undefined" && typeof navigator === "undefined") {
    return false;
  }

  const globalFlag =
    typeof window !== "undefined" &&
    Boolean((window as typeof window & { __lawkeyConstrained?: boolean }).__lawkeyConstrained);
  if (globalFlag) {
    return true;
  }

  const connection =
    typeof navigator !== "undefined"
      ? (navigator as Navigator & {
          connection?: {
            saveData?: boolean;
            downlink?: number;
            effectiveType?: string;
          };
        }).connection
      : undefined;

  const deviceMemoryGb =
    typeof navigator !== "undefined"
      ? (navigator as Navigator & { deviceMemory?: number }).deviceMemory
      : undefined;

  return detectConstrainedMode({
    saveData: connection?.saveData,
    downlinkMbps: connection?.downlink,
    effectiveType: connection?.effectiveType,
    deviceMemoryGb,
    hardwareConcurrency: typeof navigator !== "undefined" ? navigator.hardwareConcurrency : undefined,
  });
};

export const buildConstrainedModeBootstrapScript = () => `
  (function () {
    try {
      var nav = navigator || {};
      var connection = nav.connection || {};
      var constrained = !!(
        connection.saveData ||
        (typeof connection.downlink === "number" && connection.downlink <= 1) ||
        /^(slow-2g|2g|3g)$/i.test(connection.effectiveType || "") ||
        (typeof nav.deviceMemory === "number" && nav.deviceMemory <= 4) ||
        (typeof nav.hardwareConcurrency === "number" && nav.hardwareConcurrency <= 4)
      );
      if (constrained) {
        window.__lawkeyConstrained = true;
        document.documentElement.setAttribute("data-lawkey-constrained", "1");
      }
    } catch {}
  })();
`;
