import { apiFetch, apiJson } from "./client";

export interface CatalogInfo {
  ok: boolean;
  exists: boolean;
  filename?: string;
  size?: number;
  /** Unix timestamp (seconds), per gearledger/server.py's `time.time()`. */
  modified?: number;
}

export interface CatalogUploadResult {
  ok: boolean;
  filename: string;
  size: number;
  version: number;
}

export function fetchCatalogInfo(): Promise<CatalogInfo> {
  return apiJson<CatalogInfo>("/api/catalog/info");
}

export async function uploadCatalog(file: File): Promise<CatalogUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch("/api/catalog", {
    method: "POST",
    body: formData,
    isJson: false,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error ?? "Upload failed");
  }
  return data as CatalogUploadResult;
}
