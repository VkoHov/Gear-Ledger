import { useQuery } from "@tanstack/react-query";
import { fetchCompleteness, type CompletenessLine } from "../api/reports";

function Section({
  title,
  lines,
  columns,
}: {
  title: string;
  lines: CompletenessLine[];
  columns: { key: keyof CompletenessLine; label: string }[];
}) {
  if (lines.length === 0) return null;
  return (
    <div className="mb-6">
      <h2 className="mb-2 text-sm font-semibold text-neutral-700">
        {title} ({lines.length})
      </h2>
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-200 text-neutral-500">
            <th className="px-3 py-1.5">Client</th>
            <th className="px-3 py-1.5">Article</th>
            {columns.map((col) => (
              <th key={col.key} className="px-3 py-1.5">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((line, i) => (
            <tr key={`${line.client}-${line.artikul}-${i}`} className="border-b border-neutral-100">
              <td className="px-3 py-1.5">{line.client}</td>
              <td className="px-3 py-1.5">{line.artikul}</td>
              {columns.map((col) => (
                <td key={col.key} className="px-3 py-1.5">
                  {line[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Completeness() {
  const query = useQuery({ queryKey: ["completeness"], queryFn: fetchCompleteness });

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Completeness</h1>

      {query.isLoading && <p className="text-neutral-500">Loading…</p>}
      {query.isError && <p className="text-red-600">Failed to load completeness report.</p>}

      {query.data && !query.data.ok && (
        <p className="text-neutral-500">
          {query.data.error === "no_quantity_column"
            ? "The uploaded catalog has no quantity column to compare against."
            : "No catalog uploaded yet."}
        </p>
      )}

      {query.data?.ok && (
        <>
          <p className="mb-4 text-sm text-neutral-500">
            {query.data.complete_count} of {query.data.total_count} catalog lines complete.
          </p>
          <Section title="Not started" lines={query.data.not_started} columns={[{ key: "ordered", label: "Ordered" }]} />
          <Section
            title="Partial"
            lines={query.data.partial}
            columns={[
              { key: "ordered", label: "Ordered" },
              { key: "recorded", label: "Recorded" },
              { key: "missing", label: "Missing" },
            ]}
          />
          <Section
            title="Over-recorded"
            lines={query.data.over_recorded}
            columns={[
              { key: "ordered", label: "Ordered" },
              { key: "recorded", label: "Recorded" },
              { key: "excess", label: "Excess" },
            ]}
          />
          <Section
            title="Not in catalog"
            lines={query.data.not_in_catalog}
            columns={[{ key: "recorded", label: "Recorded" }]}
          />
          {query.data.not_started.length === 0 &&
            query.data.partial.length === 0 &&
            query.data.over_recorded.length === 0 &&
            query.data.not_in_catalog.length === 0 && (
              <p className="text-neutral-500">Everything's complete.</p>
            )}
        </>
      )}
    </div>
  );
}
