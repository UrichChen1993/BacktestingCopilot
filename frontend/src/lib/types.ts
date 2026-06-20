export interface GridParams {
  price_lower: number;
  price_upper: number;
  grid_num: number;
}

export interface VAParams {
  total_periods: number;
  period_interval_days: number;
}

export interface BacktestRequest {
  symbol: string;
  strategy_type: "grid" | "value_averaging";
  total_capital: number;
  start_date: string;
  end_date: string;
  market_filter_enabled: boolean;
  llm_provider: string;
  grid_params?: GridParams;
  va_params?: VAParams;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface TradeRow {
  day: string;
  side: string;
  price: number;
  quantity: number;
  amount: number;
  fee: number;
  tax: number;
  reason: string;
}

export interface BacktestResponse {
  total_return: number;
  mdd: number;
  win_rate: number;
  trade_count: number;
  final_value: number;
  realized_profit: number;
  unrealized_profit: number;
  market_filter_count: number;
  warnings: string[];
  equity_curve: EquityPoint[];
  risk_level: string;
  paper_trading_ready: boolean;
  summary: string;
  suggestions: string[];
  narrative: string;
  trades: TradeRow[];
  trades_csv: string;
  report_md: string;
}

export interface OptimizeRequest {
  symbol: string;
  strategy_type: "grid" | "value_averaging";
  total_capital: number;
  start_date: string;
  end_date: string;
  max_rounds: number;
  llm_provider: string;
  search_space: Record<string, number[]>;
}

export interface RoundResult {
  round_num: number;
  params: Record<string, unknown>;
  score: number;
  total_return: number;
  mdd: number;
  win_rate: number;
  trade_count: number;
}

export interface OptimizeResponse {
  best_params: Record<string, unknown>;
  best_score: number;
  stopped_reason: string;
  all_rounds: RoundResult[];
}

export interface AdvisorResponse {
  recommended_strategy: string;
  confidence_level: string;
  reason: string[];
  suggested_parameters: Record<string, unknown>;
  risk_notes: string[];
  narrative: string;
}

export interface ApiError {
  detail: string;
  error_code: string;
}
