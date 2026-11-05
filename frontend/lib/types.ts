export type Platform = "flipkart" | "croma" | "myntra";
export type JobStatus = "pending" | "processing" | "completed" | "failed";
export type ResultStatus = "in_stock" | "out_of_stock" | "not_listed" | "failed";
export type FailureReason =
  | "blocked"
  | "timeout"
  | "parse_error"
  | "availability_unknown"
  | "unexpected";

export interface Product {
  url: string;
  title: string;
  brand: string;
  model: string;
  category: string;
  attributes: Record<string, string>;
  image_url: string | null;
}

export interface MatchResult {
  matched: boolean;
  score: number;
  checks: Record<string, boolean>;
  reasons: string[];
}

export interface MarketplaceResult {
  platform: Platform;
  status: ResultStatus;
  title: string | null;
  url: string | null;
  image_url: string | null;
  match: MatchResult | null;
  failure_reason: FailureReason | null;
  candidates_checked: number;
}

export interface SearchJob {
  search_id: string;
  status: JobStatus;
  source_url: string;
  source_product: Product | null;
  results: MarketplaceResult[] | null;
  error: string | null;
}
