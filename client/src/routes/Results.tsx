import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { clearResults, deleteResult, fetchClients, fetchResults, updateResult, type ResultRow } from "../api/results";

const columnHelper = createColumnHelper<ResultRow>();

export function Results() {
  const [clientFilter, setClientFilter] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingQuantity, setEditingQuantity] = useState("");
  const queryClient = useQueryClient();

  const clientsQuery = useQuery({ queryKey: ["clients"], queryFn: fetchClients });
  const resultsQuery = useQuery({
    queryKey: ["results", clientFilter],
    queryFn: () => fetchResults(clientFilter || undefined),
  });

  const invalidateResults = () => queryClient.invalidateQueries({ queryKey: ["results"] });

  const updateMutation = useMutation({
    mutationFn: ({ id, quantity }: { id: number; quantity: number }) => updateResult(id, { quantity }),
    onSuccess: () => {
      invalidateResults();
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteResult(id),
    onSuccess: invalidateResults,
  });

  const clearMutation = useMutation({
    mutationFn: () => clearResults(clientFilter || undefined),
    onSuccess: invalidateResults,
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor("artikul", { header: "Article" }),
      columnHelper.accessor("client", { header: "Client" }),
      columnHelper.accessor("quantity", {
        header: "Quantity",
        cell: (info) => {
          const row = info.row.original;
          if (editingId === row.id) {
            return (
              <input
                type="number"
                min={0}
                value={editingQuantity}
                onChange={(e) => setEditingQuantity(e.target.value)}
                className="w-20 rounded border border-neutral-300 px-2 py-1"
                autoFocus
              />
            );
          }
          return info.getValue();
        },
      }),
      columnHelper.accessor("weight", { header: "Weight" }),
      columnHelper.accessor("brand", { header: "Brand" }),
      columnHelper.accessor("sale_price", { header: "Sale price" }),
      columnHelper.accessor("total_price", { header: "Total" }),
      columnHelper.accessor("last_updated", { header: "Updated" }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const row = info.row.original;
          if (editingId === row.id) {
            return (
              <div className="flex gap-2">
                <button
                  type="button"
                  className="text-sm text-blue-600"
                  onClick={() => updateMutation.mutate({ id: row.id, quantity: Number(editingQuantity) })}
                >
                  Save
                </button>
                <button type="button" className="text-sm text-neutral-500" onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </div>
            );
          }
          return (
            <div className="flex gap-2">
              <button
                type="button"
                className="text-sm text-blue-600"
                onClick={() => {
                  setEditingId(row.id);
                  setEditingQuantity(String(row.quantity));
                }}
              >
                Edit
              </button>
              <button
                type="button"
                className="text-sm text-red-600"
                onClick={() => {
                  if (window.confirm(`Delete ${row.artikul} for ${row.client}?`)) {
                    deleteMutation.mutate(row.id);
                  }
                }}
              >
                Delete
              </button>
            </div>
          );
        },
      }),
    ],
    [editingId, editingQuantity, updateMutation, deleteMutation],
  );

  const table = useReactTable({
    data: resultsQuery.data?.results ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Results</h1>
        <div className="flex items-center gap-3">
          <select
            value={clientFilter}
            onChange={(e) => setClientFilter(e.target.value)}
            className="rounded border border-neutral-300 px-2 py-1 text-sm"
          >
            <option value="">All clients</option>
            {clientsQuery.data?.clients.map((client) => (
              <option key={client} value={client}>
                {client}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-600"
            onClick={() => {
              const label = clientFilter ? `all results for ${clientFilter}` : "all results";
              if (window.confirm(`Clear ${label}?`)) {
                clearMutation.mutate();
              }
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {resultsQuery.isLoading && <p className="text-neutral-500">Loading…</p>}
      {resultsQuery.isError && <p className="text-red-600">Failed to load results.</p>}

      {resultsQuery.data && (
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b border-neutral-200">
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-3 py-2 font-medium text-neutral-500">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-b border-neutral-100">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-neutral-400">
                  No results.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
