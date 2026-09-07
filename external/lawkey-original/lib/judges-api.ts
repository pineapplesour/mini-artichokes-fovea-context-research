const API_BASE = process.env.EXPO_PUBLIC_LAWKEY_API_BASE ?? "";

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("UNAUTHORIZED");
    }
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export type JudgeSummary = {
  judgeId: string;
  name: string;
  hanja: string;
  appearanceCount: number;
  firstSeen: string;
  lastSeen: string;
  courts: string[];
};

export type JudgeCareerEntry = { court: string; year: number; count: number; role: string };
export type JudgeCase = {
  canonicalId: string;
  caseNumber: string;
  court: string;
  decisionDate: string;
  role: string;
};
export type JudgeReview = { reviewId: string; rating: number; body: string; createdAt: number };
export type JudgeCasesPage = { total: number; offset: number; limit: number; cases: JudgeCase[] };
export type JudgeSummaryRecord = {
  summary: string;
  samplesUsed: number;
  totalCases: number;
  createdAt: number;
  generatedBy: string;
};
export type JudgeProfilePayload = {
  judge: JudgeSummary & { clusterMethod: string };
  career: JudgeCareerEntry[];
  casesPage: JudgeCasesPage;
  reviews: { reviews: JudgeReview[]; averageRating: number; reviewCount: number };
  summary: JudgeSummaryRecord | null;
};

export type JudgePrecedentText = {
  canonicalId: string;
  caseNumber: string;
  caseName: string;
  court: string;
  decisionDate: string;
  fullText: string;
};

export type JudgePredictPayload = {
  judge: JudgeSummary;
  answerMarkdown: string;
  samplesUsed: number;
  totalCases?: number;
  error?: string;
};

const PASSWORD_KEY = "lawkey-judges-password-v1";

export function getStoredJudgesPassword(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.sessionStorage.getItem(PASSWORD_KEY) || "";
  } catch {
    return "";
  }
}

export function storeJudgesPassword(password: string): void {
  if (typeof window === "undefined") return;
  try {
    if (password) window.sessionStorage.setItem(PASSWORD_KEY, password);
    else window.sessionStorage.removeItem(PASSWORD_KEY);
  } catch {
    /* ignore */
  }
}

export async function authJudges(password: string): Promise<void> {
  await postJson<{ ok: boolean }>("/api/judges/auth", { password });
}

export async function searchJudges(password: string, query: string): Promise<JudgeSummary[]> {
  const data = await postJson<{ results: JudgeSummary[] }>("/api/judges/search", {
    password,
    q: query,
    limit: 30,
  });
  return data.results;
}

export async function fetchJudgeProfile(password: string, judgeId: string): Promise<JudgeProfilePayload> {
  return postJson<JudgeProfilePayload>(`/api/judges/${encodeURIComponent(judgeId)}`, {
    password,
    caseLimit: 20,
    caseOffset: 0,
  });
}

export async function fetchJudgeCases(
  password: string,
  judgeId: string,
  offset: number,
  limit: number = 20,
): Promise<JudgeCasesPage> {
  return postJson<JudgeCasesPage>(`/api/judges/${encodeURIComponent(judgeId)}/cases`, {
    password,
    offset,
    limit,
  });
}

export async function summarizeJudge(
  password: string,
  judgeId: string,
  clientId: string,
): Promise<{ summary: JudgeSummaryRecord; fromCache: boolean }> {
  return postJson(`/api/judges/${encodeURIComponent(judgeId)}/summarize`, {
    password,
    clientId,
  });
}

export async function fetchPrecedentText(password: string, canonicalId: string): Promise<JudgePrecedentText> {
  return postJson(`/api/judges/precedent/${encodeURIComponent(canonicalId)}`, { password });
}

export async function predictWithJudge(
  password: string,
  judgeId: string,
  question: string,
  clientId: string,
): Promise<JudgePredictPayload> {
  return postJson<JudgePredictPayload>(`/api/judges/${encodeURIComponent(judgeId)}/predict`, {
    password,
    question,
    clientId,
  });
}

export async function submitJudgeReview(
  password: string,
  judgeId: string,
  rating: number,
  body: string,
  clientId: string,
): Promise<JudgeProfilePayload["reviews"]> {
  return postJson(`/api/judges/${encodeURIComponent(judgeId)}/reviews`, {
    password,
    rating,
    body,
    clientId,
  });
}
