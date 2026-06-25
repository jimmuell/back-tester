export type VerdictStatus = "pass" | "caution" | "fail" | "inconclusive" | "info";

export interface Metrics {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  net_profit: number;
  gross_profit: number;
  gross_loss: number;
  avg_win: number;
  avg_loss: number;
  expectancy: number;
  profit_factor: number | null;
  payoff_ratio: number | null;
  max_drawdown: number;
  longest_win_streak: number;
  longest_loss_streak: number;
  equity_curve: number[];
}

export interface Shuffle {
  n_iterations: number;
  net_profit: number;
  risk_of_ruin: number;
  ruin_threshold: number;
  max_drawdown_pctiles: Record<string, number>;
}

export interface Bootstrap {
  n_iterations: number;
  ci_level: number;
  expectancy_point: number;
  expectancy_ci: [number, number];
  net_profit_point: number;
  net_profit_ci: [number, number];
  win_rate_point: number;
  win_rate_ci: [number, number];
  profit_factor_point: number | null;
  profit_factor_ci: [number | null, number | null];
  n_inf_pf: number;
}

export interface Split {
  oos_fraction: number;
  split_time: string;
  is_trades: number;
  oos_trades: number;
  is_expectancy: number;
  oos_expectancy: number;
  is_net_profit: number;
  oos_net_profit: number;
  is_win_rate: number;
  oos_win_rate: number;
  edge_decayed: boolean;
  expectancy_ratio: number | null;
}

export interface WalkForwardWindow {
  index: number;
  start_time: string;
  end_time: string;
  n_trades: number;
  expectancy: number;
  net_profit: number;
  win_rate: number;
  profit_factor: number | null;
  max_drawdown: number;
}

export interface WalkForward {
  n_windows: number;
  scheme: string;
  pct_windows_positive: number;
  expectancy_mean: number;
  expectancy_std: number;
  windows: WalkForwardWindow[];
}

export interface BuyHold {
  strategy_net: number;
  buy_hold_net: number;
  beats_buy_hold: boolean;
  start_price: number;
  end_price: number;
  start_time: string;
  end_time: string;
  instrument_symbol: string;
}

export interface RandomEntry {
  n_iterations: number;
  n_trades: number;
  long_fraction: number;
  strategy_net: number;
  strategy_expectancy: number;
  net_percentile_rank: number;
  threshold: number;
  beats_random: boolean;
  random_net_pctiles: Record<string, number>;
}

export interface RegimeStats {
  total_trades: number;
  win_rate: number;
  expectancy: number;
  net_profit: number;
  profit_factor: number | null;
}

export interface RegimeBreakdown {
  scheme: string;
  params: Record<string, unknown>;
  trade_counts: Record<string, number>;
  per_regime: Record<string, RegimeStats>;
}

export interface Finding {
  key: string;
  title: string;
  status: VerdictStatus;
  headline: string;
  detail: string;
  stat: number | null;
}

export interface Verdict {
  overall: VerdictStatus;
  summary: string;
  findings: Finding[];
}

export interface ValidationResponse {
  metrics: Metrics;
  shuffle: Shuffle;
  bootstrap: Bootstrap;
  split: Split | null;
  walk_forward: WalkForward | null;
  buy_hold: BuyHold | null;
  random_entry: RandomEntry | null;
  regimes: Record<string, RegimeBreakdown>;
  skipped: string[];
  verdict: Verdict;
}
