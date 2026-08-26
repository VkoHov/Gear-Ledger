import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { lookupCatalogCode, fetchStockPreview, type CodeMatch } from "../api/manualEntry";
import { createResult } from "../api/results";

export function ManualEntry() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [resolved, setResolved] = useState<{ artikul: string; client: string } | null>(null);
  const [candidates, setCandidates] = useState<CodeMatch[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [quantity, setQuantity] = useState("1");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const lookupMutation = useMutation({
    mutationFn: (submittedCode: string) => lookupCatalogCode(submittedCode),
    onSuccess: (result) => {
      setNotFound(false);
      setCandidates(null);
      setResolved(null);
      if (!result.match_client || !result.match_artikul) {
        setNotFound(true);
        return;
      }
      if (result.multi_match.length > 1) {
        setCandidates(result.multi_match);
        return;
      }
      setResolved({ artikul: result.match_artikul, client: result.match_client });
      setQuantity("1");
    },
  });

  const stockQuery = useQuery({
    queryKey: ["stock-preview", resolved?.artikul, resolved?.client],
    queryFn: () => fetchStockPreview(resolved!.artikul, resolved!.client),
    enabled: resolved !== null,
  });

  const addMutation = useMutation({
    mutationFn: () =>
      createResult({ artikul: resolved!.artikul, client: resolved!.client, quantity: Number(quantity) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["results"] });
      setSuccessMessage(`Added ${quantity} × ${resolved!.artikul} for ${resolved!.client}`);
      setCode("");
      setResolved(null);
      setCandidates(null);
      setNotFound(false);
      setQuantity("1");
    },
  });

  function handleLookup(event: FormEvent) {
    event.preventDefault();
    setSuccessMessage(null);
    const trimmed = code.trim();
    if (trimmed) {
      lookupMutation.mutate(trimmed);
    }
  }

  function pickCandidate(candidate: CodeMatch) {
    setCandidates(null);
    setResolved({ artikul: candidate.artikul, client: candidate.client });
    setQuantity("1");
  }

  const preview = stockQuery.data;
  const remaining = preview?.tracked ? (preview.remaining ?? 0) : null;
  const outOfStock = preview?.tracked === true && remaining !== null && remaining <= 0;
  const maxQuantity = preview?.tracked ? Math.max(remaining ?? 0, 0) : undefined;

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Manual Entry</h1>

      <form onSubmit={handleLookup} className="mb-6 flex max-w-lg items-end gap-3">
        <label className="flex-1 text-sm text-neutral-600">
          Article code
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="e.g. ABC123"
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={lookupMutation.isPending}
          className="rounded bg-neutral-900 px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          {lookupMutation.isPending ? "Searching…" : "Find and add"}
        </button>
      </form>

      {successMessage && <p className="mb-4 text-sm text-green-700">{successMessage}</p>}
      {lookupMutation.isError && <p className="mb-4 text-sm text-red-600">Lookup failed.</p>}
      {notFound && <p className="mb-4 text-sm text-neutral-500">No match found for "{code}".</p>}

      {candidates && (
        <div className="mb-6 max-w-lg rounded border border-neutral-200 p-4">
          <p className="mb-2 text-sm text-neutral-600">
            This code matches more than one client — pick which one:
          </p>
          <div className="flex flex-col gap-2">
            {candidates.map((candidate) => (
              <button
                key={`${candidate.client}-${candidate.artikul}`}
                type="button"
                onClick={() => pickCandidate(candidate)}
                className="rounded border border-neutral-300 px-3 py-2 text-left text-sm hover:bg-neutral-50"
              >
                {candidate.artikul} → {candidate.client}
              </button>
            ))}
          </div>
        </div>
      )}

      {resolved && stockQuery.isLoading && <p className="text-neutral-500">Checking stock…</p>}
      {resolved && stockQuery.isError && <p className="text-red-600">Failed to check stock.</p>}

      {resolved && preview && (
        <div className="max-w-lg rounded border border-neutral-200 p-4">
          <p className="mb-2 font-medium">
            {resolved.artikul} → {resolved.client}
          </p>

          {preview.tracked ? (
            <p className="mb-3 text-sm text-neutral-600">
              Stock: {preview.stock}
              {preview.breakdown && preview.breakdown.length > 1 && ` (${preview.breakdown.join(" + ")})`} · already
              added: {preview.already_added} · remaining: {remaining}
            </p>
          ) : (
            <p className="mb-3 text-sm text-neutral-500">
              Catalog has no stock tracking for this item — quantity is unbounded.
            </p>
          )}

          {outOfStock ? (
            <p className="text-sm text-red-600">
              Out of stock: {preview.already_added} of {preview.stock} already recorded for this client.
            </p>
          ) : (
            <div className="flex items-end gap-3">
              <label className="text-sm text-neutral-600">
                Quantity
                <input
                  type="number"
                  min={1}
                  max={maxQuantity}
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="mt-1 w-24 rounded border border-neutral-300 px-3 py-2"
                />
              </label>
              <button
                type="button"
                disabled={addMutation.isPending || Number(quantity) < 1}
                onClick={() => addMutation.mutate()}
                className="rounded bg-neutral-900 px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                {addMutation.isPending ? "Adding…" : "Add"}
              </button>
            </div>
          )}

          {addMutation.isError && (
            <p className="mt-2 text-sm text-red-600">
              {addMutation.error instanceof Error ? addMutation.error.message : "Failed to add"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
