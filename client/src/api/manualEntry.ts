import { apiJson } from "./client";

export interface CodeMatch {
  client: string;
  artikul: string;
}

export interface CodeLookupResult {
  ok: boolean;
  match_client: string | null;
  match_artikul: string | null;
  multi_match: CodeMatch[];
}

export function lookupCatalogCode(code: string): Promise<CodeLookupResult> {
  const params = new URLSearchParams({ code });
  return apiJson<CodeLookupResult>(`/api/catalog/lookup?${params.toString()}`);
}

export interface StockPreview {
  ok: boolean;
  tracked: boolean;
  stock: number | null;
  breakdown: number[] | null;
  already_added: number;
  remaining: number | null;
}

export function fetchStockPreview(artikul: string, client: string): Promise<StockPreview> {
  const params = new URLSearchParams({ artikul, client });
  return apiJson<StockPreview>(`/api/catalog/stock?${params.toString()}`);
}
