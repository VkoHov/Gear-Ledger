import { useAuth } from "../auth/AuthContext";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8081";

export function Settings() {
  const { logout } = useAuth();

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Settings</h1>
      <div className="rounded border border-neutral-200 p-4">
        <p className="text-sm text-neutral-500">API server</p>
        <p className="font-mono text-sm">{API_BASE_URL}</p>
      </div>
      <button
        type="button"
        onClick={logout}
        className="mt-4 rounded border border-neutral-300 px-3 py-2 text-sm"
      >
        Log out
      </button>
    </div>
  );
}
