import type { ApiResponse, SearchResponseData } from "../types/airportSearchTypes";
import { API_ROUTES } from "../constants/apiConstants";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export async function searchAirports(
  query: string,
  limit: number = 10,
  correlationId?: string,
  signal?: AbortSignal
): Promise<ApiResponse<SearchResponseData>> {
  const url = new URL(`${API_BASE_URL}${API_ROUTES.SEARCH}`);
  url.searchParams.append("q", query);
  url.searchParams.append("limit", limit.toString());

  const headers: HeadersInit = {
    "Accept": "application/json"
  };
  
  if (correlationId) {
    headers["X-Correlation-ID"] = correlationId;
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers,
    signal
  });

  const json: ApiResponse<SearchResponseData> = await response.json();

  if (!response.ok || json.status === "ERROR") {
    const errorMsg = json.errors?.[0]?.message || `Search failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return json;
}
