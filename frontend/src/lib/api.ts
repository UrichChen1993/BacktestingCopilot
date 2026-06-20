import type {
  BacktestRequest, BacktestResponse,
  OptimizeRequest, OptimizeResponse,
  AdvisorResponse, ApiError,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      detail: "Unknown error",
      error_code: "UNKNOWN",
    }));
    throw err;
  }
  return res.json() as Promise<T>;
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  const res = await fetch(`${BASE}/api/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<BacktestResponse>(res);
}

export async function runOptimize(req: OptimizeRequest): Promise<OptimizeResponse> {
  const res = await fetch(`${BASE}/api/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<OptimizeResponse>(res);
}

export async function getAdvisor(params: {
  symbol: string;
  start_date: string;
  end_date: string;
  total_capital: number;
  llm_provider: string;
}): Promise<AdvisorResponse> {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();
  const res = await fetch(`${BASE}/api/advisor?${qs}`);
  return handleResponse<AdvisorResponse>(res);
}
