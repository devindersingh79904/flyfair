export type ApiStatus = "SUCCESS" | "ERROR";

export interface ApiError {
  code: string;
  message: string;
  field?: string | null;
}

export interface ResponseMeta {
  limit?: number;
  count?: number;
  hasMore?: boolean;
  latencyMs?: number;
}

export interface ApiResponse<T> {
  timestamp: string;
  correlationId: string;
  status: ApiStatus;
  message: string;
  data: T | null;
  errors: ApiError[];
  meta: ResponseMeta;
}

export interface AirportSummary {
  id?: string;
  iata: string;
  name: string;
  city: string;
  region?: string | null;
  country: string;
  countryCode: string;
}

export interface SearchResult {
  id: string;
  type: "AIRPORT" | "CITY_GROUP" | "REGION_GROUP";
  code?: string;
  displayName: string;
  city?: string | null;
  region?: string | null;
  country: string;
  countryCode: string;
  score: number;
  matchReason: string;
  airports: AirportSummary[];
}

export interface SearchResponseData {
  results: SearchResult[];
}
