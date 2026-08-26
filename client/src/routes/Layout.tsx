import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const navItems = [
  { to: "/results", label: "Results" },
  { to: "/catalog", label: "Catalog" },
  { to: "/completeness", label: "Completeness" },
  { to: "/invoice", label: "Invoice" },
  { to: "/scan", label: "Scan" },
  { to: "/manual-entry", label: "Manual Entry" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { logout } = useAuth();

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-3">
        <span className="font-semibold">Gear Ledger</span>
        <nav className="flex gap-4 text-sm">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? "font-semibold text-neutral-900" : "text-neutral-500 hover:text-neutral-900"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button type="button" onClick={logout} className="text-sm text-neutral-500 hover:text-neutral-900">
          Log out
        </button>
      </header>
      <main className="mx-auto max-w-6xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
