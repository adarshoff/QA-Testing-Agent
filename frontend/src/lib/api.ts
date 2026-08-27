const BASE = `${import.meta.env.BASE_URL}api`;

export interface Bug {
  bugId: string;
  category: string;
  severity: string;
  elementDescription?: string;
  element?: string;
  locationOnScreen?: string;
  description: string;
  cssfix?: string;
  htmlFix?: string;
  devtoolsCommand?: string;
  wcagCriterion?: string;
  url?: string;
  label?: string;
  viewport?: string;
}

export interface NetworkIssue {
  type: string;
  severity: string;
  url: string;
  method?: string;
  statusCode?: number;
  responseTimeMs?: number;
  description: string;
  fix: string;
}

export interface FigmaDeviation {
  deviationId: string;
  severity: string;
  element: string;
  figmaValue?: string;
  actualValue?: string;
  description: string;
  cssFix?: string;
  devtoolsCommand?: string;
}

export interface Fix {
  bugId: string;
  category: string;
  severity: string;
  devtoolsCommand: string;
  cssFix?: string;
  htmlFix?: string;
  description: string;
  element?: string;
  label?: string;
  url?: string;
}

export interface PerformanceMetrics {
  initialLoadMs?: number;
  pagesScanned?: number;
  totalRequests?: number;
  errorCount?: number;
  slowRequestCount?: number;
}

export interface DomA11yBug {
  id: string;
  impact: string;
  description: string;
  help: string;
  helpUrl: string;
  html?: string;
}

export interface SecurityBug {
  type: string;
  severity: string;
  description: string;
  url?: string;
}

export interface HealingEvent {
  fieldKey: string;
  label: string;
  originalStrategy: string;
  healedStrategy: string;
  description: string;
}

export interface DesignTokenValue {
  value: string;
  sources: string[];
}

export interface DesignInconsistency {
  tokenType: string;
  component: string;
  valuesFound: DesignTokenValue[];
  severity: string;
  description: string;
  recommendation?: string;
}

export interface ScanData {
  scanId: string;
  userId: string;
  url: string;
  qualityScore: number;
  figmaMatchScore: number;
  allBugs: Bug[];
  functionalBugs: any[];
  domA11yBugs: DomA11yBug[];
  securityBugs: SecurityBug[];
  networkIssues: NetworkIssue[];
  figmaDeviations: FigmaDeviation[];
  fixes: Fix[];
  newBugs: Bug[];
  pagesVisited: string[];
  performanceMetrics: PerformanceMetrics;
  screenshotsMeta: any[];
  healingEvents: HealingEvent[];
  designInconsistencies: DesignInconsistency[];
  designConsistencyScore: number;
  createdAt: string;
  status?: string;
  error?: string;
}

export interface HistoryScan {
  scanId: string;
  url: string;
  createdAt: string;
  qualityScore: number;
  figmaMatchScore: number;
  totalBugs: number;
  criticalCount: number;
  seriousCount: number;
  moderateCount: number;
  newBugsCount: number;
  pagesScanned: number;
  networkIssues: number;
  performanceMetrics: PerformanceMetrics;
}

export async function startScan(url: string, figmaBase64?: string): Promise<ScanData> {
  const res = await fetch(`${BASE}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId: "default-user", url, figmaBase64 }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getHistory(): Promise<{ scans: HistoryScan[] }> {
  const res = await fetch(`${BASE}/history/default-user`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getReportUrl(scanId: string): string {
  return `${BASE}/scan/${scanId}/report`;
}
