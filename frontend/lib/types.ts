export type Platform = "flipkart" | "croma" | "myntra";
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

export interface ClosestListing {
  title: string;
  url: string;
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
  search_url: string | null;
  closest_listing: ClosestListing | null;
}

/** One line of the search stream. */
export interface SearchEvent {
  type: "accepted" | "product" | "result" | "completed" | "failed";
  search_id: string;
  product: Product | null;
  platforms: Platform[] | null;
  result: MarketplaceResult | null;
  error: string | null;
}
