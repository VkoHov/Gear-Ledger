import { apiJson } from "./client";

export interface ResultRow {
  id: number;
  artikul: string;
  client: string;
  quantity: number;
  weight: number | null;
  last_updated: string;
  brand: string | null;
  description: string | null;
  sale_price: number | null;
  total_price: number | null;
  created_at: string;
}

interface ResultsResponse {
  ok: boolean;
  results: ResultRow[];
}

interface ClientsResponse {
  ok: boolean;
  clients: string[];
}

export function fetchResults(client?: string): Promise<ResultsResponse> {
  const query = client ? `?client=${encodeURIComponent(client)}` : "";
  return apiJson<ResultsResponse>(`/api/results${query}`);
}

export function fetchClients(): Promise<ClientsResponse> {
  return apiJson<ClientsResponse>("/api/clients");
}

export interface CreateResultInput {
  artikul: string;
  client: string;
  quantity: number;
}

export function createResult(input: CreateResultInput): Promise<{ ok: boolean }> {
  return apiJson<{ ok: boolean }>("/api/results", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateResult(id: number, fields: Partial<ResultRow>): Promise<{ ok: boolean }> {
  return apiJson<{ ok: boolean }>(`/api/results/${id}`, {
    method: "PUT",
    body: JSON.stringify(fields),
  });
}

export function deleteResult(id: number): Promise<{ ok: boolean }> {
  return apiJson<{ ok: boolean }>(`/api/results/${id}`, { method: "DELETE" });
}

export function clearResults(client?: string): Promise<{ ok: boolean; deleted: number }> {
  return apiJson<{ ok: boolean; deleted: number }>("/api/results/clear", {
    method: "POST",
    body: JSON.stringify(client ? { client } : {}),
  });
}
