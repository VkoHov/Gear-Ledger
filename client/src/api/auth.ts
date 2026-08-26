import { apiJson } from "./client";

export interface AuthResponse {
  access_token: string;
  tenant_id: string;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return apiJson<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signup(email: string, password: string): Promise<AuthResponse> {
  return apiJson<AuthResponse>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}
