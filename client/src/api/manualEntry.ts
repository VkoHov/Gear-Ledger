import { apiJson } from "./client";

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
