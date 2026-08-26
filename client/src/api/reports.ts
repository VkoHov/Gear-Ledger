import { apiFetch, apiJson } from "./client";

export interface CompletenessLine {
  client: string;
  artikul: string;
  ordered?: number;
  recorded?: number;
  missing?: number;
  excess?: number;
}

export interface CompletenessReport {
  ok: boolean;
  error?: string;
  not_started: CompletenessLine[];
  partial: CompletenessLine[];
  over_recorded: CompletenessLine[];
  not_in_catalog: CompletenessLine[];
  complete_count: number;
  total_count: number;
}

export function fetchCompleteness(): Promise<CompletenessReport> {
  return apiJson<CompletenessReport>("/api/completeness");
}

export async function generateInvoice(weightPrice: number): Promise<Blob> {
  const response = await apiFetch("/api/invoice", {
    method: "POST",
    body: JSON.stringify({ weight_price: weightPrice }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error ?? "Invoice generation failed");
  }
  return response.blob();
}
