import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Catalog } from "./routes/Catalog";
import { ComingSoon } from "./routes/ComingSoon";
import { Completeness } from "./routes/Completeness";
import { Invoice } from "./routes/Invoice";
import { Layout } from "./routes/Layout";
import { Login } from "./routes/Login";
import { ManualEntry } from "./routes/ManualEntry";
import { Results } from "./routes/Results";
import { Settings } from "./routes/Settings";
import { Signup } from "./routes/Signup";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/results" replace />} />
          <Route path="/results" element={<Results />} />
          <Route path="/catalog" element={<Catalog />} />
          <Route path="/completeness" element={<Completeness />} />
          <Route path="/invoice" element={<Invoice />} />
          <Route path="/scan" element={<ComingSoon title="Scan" />} />
          <Route path="/manual-entry" element={<ManualEntry />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/results" replace />} />
    </Routes>
  );
}
