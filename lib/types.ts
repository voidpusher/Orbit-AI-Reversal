// UI-facing contracts mirroring the Orbit API responses.

export type AnalysisStatus =
  | "queued"
  | "running"
  | "generating_report"
  | "completed"
  | "failed"
  | "cancelled";

export interface AnalysisOptions {
  deep_crawl: boolean;
  max_pages: number;
  capture_network_requests: boolean;
  evidence_mode?: "crawl" | "har";
}

export interface SanitizedHarEntry {
  url: string;
  method: string;
  status: number;
  resource_type?: string;
  content_type?: string;
  cache_control?: string;
  server?: string;
}

export interface HarImportPayload {
  target_url: string;
  entries: SanitizedHarEntry[];
  authorized_public_analysis: true;
}

export interface Analysis {
  id: string;
  target_url: string;
  status: AnalysisStatus;
  progress: number;
  options: AnalysisOptions;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
  event_stream_url: string;
  report_id: string | null;
  error_code: string | null;
}

export interface AnalysisEvent {
  sequence: number;
  kind: string;
  message: string;
  payload: Record<string, unknown>;
  occurred_at: string;
}

export interface Confidenced {
  summary: string;
  confidence: number;
}

export interface ArchNode {
  id: string;
  label: string;
  kind: string;
  confidence: number;
  classification?: "observed" | "inferred";
  role?: string;
  responsibilities?: string[];
  evidence?: string[];
}

export interface ArchConnection {
  from: string;
  to: string;
  label: string;
  protocol: string;
  confidence: number;
  classification: "observed" | "inferred";
  evidence: string[];
}

export interface ArchRequestFlow {
  name: string;
  steps: string[];
  transport: string;
  confidence: number;
  classification: "observed" | "inferred";
  evidence: string[];
}

export interface ArchTrustBoundary {
  name: string;
  between: string[];
  implication: string;
  confidence: number;
  evidence: string[];
}

export interface ArchPattern {
  title: string;
  detail: string;
  confidence: number;
  classification: "observed" | "inferred";
  evidence: string[];
}

export interface Detection {
  name: string;
  category: string;
  confidence: number;
  evidence: string[];
}

export interface Feature {
  name: string;
  description: string;
  confidence: number;
  classification: string;
  evidence: string[];
}

export interface Entity {
  name: string;
  fields: string[];
  confidence: number;
}

export interface Insight {
  title: string;
  detail: string;
  confidence: number;
  classification: string;
}

export type FindingStatus = "good" | "warn" | "bad" | "info";

export interface Finding {
  title: string;
  detail: string;
  status: FindingStatus;
  evidence?: string;
}

export interface SectionMetric {
  label: string;
  value: string;
}

export interface GradedSection extends Confidenced {
  grade?: string;
  score?: number;
  findings: Finding[];
  metrics?: SectionMetric[];
  // Legacy shape (pre-deep-analysis reports) may still carry items.
  items?: Insight[];
}

export interface RenderingSection extends Confidenced {
  strategy: string;
  region: string | null;
  findings: Finding[];
  metrics?: SectionMetric[];
}

export interface ReportDocument {
  meta: {
    product_name: string;
    host: string;
    url: string;
    pages_explored: number;
    evidence_count: number;
    features_count: number;
    technologies_count: number;
    insights_count: number;
    overall_confidence: number;
    confidence_band: string;
    generated_at: string;
    model_name: string;
    region?: string;
    deep_findings?: number;
    access_limited?: boolean;
    access_statuses?: number[];
  };
  overview: {
    headline: string;
    summary: string;
    metrics: { value: string; label: string; sub: string }[];
  };
  architecture: Confidenced & {
    nodes: ArchNode[];
    edges: string[][];
    evidence: string[];
    reasoning?: string;
    connections?: ArchConnection[];
    layers?: { name: string; node_ids: string[] }[];
    request_flows?: ArchRequestFlow[];
    trust_boundaries?: ArchTrustBoundary[];
    patterns?: ArchPattern[];
    unknowns?: string[];
  };
  user_flows: Confidenced & { flows: { name: string; steps: string[]; confidence: number }[]; reasoning?: string };
  features: Confidenced & { items: Feature[] };
  entities: Confidenced & { items: Entity[]; relationships: { from: string; to: string; kind: string }[]; reasoning?: string };
  permissions: Confidenced & { roles: { name: string; capabilities: string[] }[]; reasoning?: string };
  database: Confidenced & { items: Entity[]; relationships: { from: string; to: string; kind: string }[]; reasoning?: string };
  api: Confidenced & {
    style: string;
    endpoints: { method: string; path: string; confidence: number; note: string }[];
    evidence: string[];
    spec?: { title: string | null; version: string | null; path_count: number } | null;
    findings?: Finding[];
  };
  tech_stack: Confidenced & { items: Detection[]; categories: string[] };
  integrations: Confidenced & { items: Detection[] };
  insights: Confidenced & { items: Insight[]; reasoning?: string };
  infrastructure: Confidenced & { items: { title: string; detail: string; confidence: number }[] };
  security: GradedSection;
  performance?: GradedSection;
  rendering?: RenderingSection;
  seo?: GradedSection;
  privacy?: GradedSection;
  domain?: GradedSection;
}

export interface ReportListItem {
  id: string;
  analysis_id: string;
  target_url: string;
  product_name: string;
  headline: string;
  overall_confidence: number;
  pages_explored: number;
  features_count: number;
  is_favorite: boolean;
  label: string | null;
  model_name: string;
  published_at: string;
}

export interface ReportDetail extends ReportListItem {
  summary: string;
  evidence_count: number;
  document: ReportDocument;
}

export interface ReportListResponse {
  items: ReportListItem[];
  next_cursor: string | null;
}

export interface Stats {
  total_analyses: number;
  completed_reports: number;
  favorites: number;
  average_confidence: number;
}

export interface Usage {
  analyses_this_month: number;
  monthly_limit: number | null;
}

export interface Me {
  id: string;
  email: string;
  name: string;
  organization: string;
  organization_id: string;
  plan: string;
  role: string;
  usage: Usage;
}

export interface AuthResult {
  token: string;
  expires_at: string;
  user: { id: string; email: string; name: string; avatar_url: string | null };
  organization: string;
  plan: string;
  role: string;
}

export interface CompareSide {
  id: string;
  product_name: string;
  host: string;
  target_url: string;
  overall_confidence: number;
  pages_explored: number;
  evidence_count: number;
  features_count: number;
  technologies_count: number;
}

export interface TechDiffItem {
  name: string;
  category: string;
  confidence: number;
}

export interface Comparison {
  a: CompareSide;
  b: CompareSide;
  similarity: number;
  confidence_delta: number;
  headline: string;
  shared_tech: TechDiffItem[];
  only_a_tech: TechDiffItem[];
  only_b_tech: TechDiffItem[];
  shared_features: string[];
  only_a_features: string[];
  only_b_features: string[];
  shared_insights: string[];
  architecture_a: string[];
  architecture_b: string[];
}
