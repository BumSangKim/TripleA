// lib/types.ts
export interface KPISummary {
  totalAssets: number;
  cash: number;
  todayProfit: number;
  todayProfitRate: number;
  riskLevel: string;
  macroScore?: number | null;
}

export type TradingMode = "mock" | "test" | "backtest" | "paper" | "live";

export interface ModeInfo {
  mode: TradingMode;
  provider: string;
  dbWriteScope: string;
  externalApi: boolean;
  orderPolicy: string;
  canWriteUserData: boolean;
  canExecuteOrders: boolean;
}

export interface MacroIndicator {
  key: string;
  name: string;
  value: number | null;
  unit: string | null;
  change: number | null;
  status: "rising" | "falling" | "stable";
  date: string | null;
  history?: number[];
}

export interface AccountSummary {
  id: number;
  name: string;
  type: string | null;
  value: number;
  profit: number;
  profitRate: number;
  accountType?: string | null;
  connectionStatus?: string | null;
  tradeStatus?: string | null;
  includeInRebalancing?: boolean;
  dataSource?: string | null;
  lastSyncedAt?: string | null;
}

export interface AccountPolicyItem {
  id: number;
  accountType: string;
  role: string;
  depositPolicy?: string | null;
  allowedProducts?: string | null;
  rebalancePriority?: string | null;
  riskNote?: string | null;
}

export interface AccountSnapshotCreate {
  totalValue: number;
  cashValue?: number;
  domesticStockValue?: number;
  foreignStockValue?: number;
  bondValue?: number;
  etfValue?: number;
  pensionValue?: number;
  altValue?: number;
  snapshotAt?: string | null;
}

export interface AccountSnapshotItem extends Required<Omit<AccountSnapshotCreate, "snapshotAt">> {
  id: number;
  accountId: number;
  snapshotAt: string | null;
  createdAt?: string | null;
}

export interface AllocationItem {
  asset: string;
  value: number;
  ratio: number;
}

export interface TargetItem {
  id?: number;
  asset_class: string;
  target_type?: string;
  currentRatio: number;
  targetRatio: number;
  deviation: number;
  level: "normal" | "warning" | "danger";
  unit?: string;
}

export interface SuggestionItem {
  asset: string;
  action: string;
  reason: string;
  deviation: number;
}

export interface RebalanceResultItem {
  id?: number | null;
  runId?: number | null;
  mode: TradingMode;
  accountId?: number | null;
  accountType?: string | null;
  assetClass: string;
  currentRatio: number;
  targetRatio: number;
  deviation: number;
  action: string;
  amount: number;
  reason: string;
  createdAt?: string | null;
}

export interface RebalanceRunResponse {
  ok: boolean;
  mode: TradingMode;
  runId: number;
  saved: number;
  results: RebalanceResultItem[];
}

export interface RiskBudgetItem {
  strategyBucket: string;
  currentRatio: number;
  targetRatio: number;
  minRatio?: number | null;
  maxRatio?: number | null;
  deviation: number;
  level: "normal" | "warning" | "danger" | string;
  action: "HOLD" | "INCREASE" | "REDUCE" | string;
  reason: string;
}

export interface ProviderSyncResult {
  ok: boolean;
  mode: TradingMode;
  provider: string;
  accountId?: number | null;
  accountMasked?: string | null;
  syncedPositions: number;
  totalValue: number;
  cashValue: number;
  message?: string | null;
}

export interface OrderItem {
  id?: number | null;
  draftId?: number | null;
  accountId?: number | null;
  assetClass: string;
  side: "BUY" | "SELL" | string;
  amount: number;
  status: string;
  reason?: string | null;
  createdAt?: string | null;
}

export interface OrderDraftResponse {
  ok: boolean;
  draftId: number;
  mode: TradingMode;
  source: string;
  status: string;
  totalAmount: number;
  itemCount: number;
  items: OrderItem[];
  message?: string | null;
}

export interface BacktestRunRequest {
  name: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  strategyMode: "triplea_dynamic";
  riskProfile: "aggressive" | "balanced" | "defensive";
  universeId: "default_global";
  rebalanceFrequency: "weekly" | "monthly" | "quarterly";
  baseCurrency: "KRW";
  feeBps: number;
  slippageBps: number;
  taxBps: number;
  dataLookbackYears: number;
}

export interface BacktestPoint {
  date: string;
  value: number;
  drawdown: number;
}

export interface BacktestPosition {
  date: string;
  assetCode: string;
  quantity: number;
  price: number;
  fxRate: number;
  marketValue: number;
  weight: number;
}

export interface BacktestTrade {
  date: string;
  assetCode: string;
  side: string;
  quantity: number;
  price: number;
  fxRate: number;
  grossAmount: number;
  fee: number;
  slippage: number;
  tax: number;
  netAmount: number;
  reason?: string | null;
}

export interface BacktestRunResponse {
  ok: boolean;
  runId: number;
  name: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  strategyMode: string;
  riskProfile: string;
  universeId: string;
  rebalanceFrequency: string;
  baseCurrency: string;
  feeBps: number;
  slippageBps: number;
  taxBps: number;
  dataLookbackYears: number;
  status: string;
  totalReturn: number;
  annualReturn: number;
  maxDrawdown: number;
  volatility: number;
  points: BacktestPoint[];
  positions: BacktestPosition[];
  trades: BacktestTrade[];
  createdAt?: string | null;
}

export interface APIErrorDetail {
  code?: string;
  message?: string;
  userAction?: string;
}

export interface TopMover {
  symbol: string;
  name: string | null;
  price: number | null;
  changeRate: number;
  contribution: number | null;
}

export interface CalendarEvent {
  id?: number;
  date: string;
  time: string | null;
  title?: string;
  event?: string;
  country: string;
  importance: "high" | "medium" | "low";
  actual?: number | null;
  forecast?: number | null;
  previous?: number | null;
}

export interface DocumentItem {
  id?: number;
  type: string;
  title: string;
  content?: string | null;
  tags?: string | null;
  url?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AlertItem {
  id: number;
  level: "info" | "warning" | "danger";
  category: string | null;
  title: string;
  message: string | null;
  is_read: boolean;
  created_at: string;
}

export interface Insights {
  macroSummary: string;
  portfolioSummary: string;
  marketRisk: string;
  recommendation: string;
}

export interface DashboardSummary {
  mode?: TradingMode;
  modeInfo?: ModeInfo | null;
  kpi: KPISummary;
  macro: MacroIndicator[];
  accounts: AccountSummary[];
  allocation: AllocationItem[];
  targets: TargetItem[];
  suggestions: SuggestionItem[];
  topMovers: TopMover[];
  calendar: CalendarEvent[];
  alerts: AlertItem[];
  insights: Insights;
}
