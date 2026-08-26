import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { fetchStockPreview } from "../api/manualEntry";
import { createResult } from "../api/results";

export function ManualEntry() {
  const queryClient = useQueryClient();
  const [artikul, setArtikul] = useState("");
  const [client, setClient] = useState("");
  const [lookedUp, setLookedUp] = useState<{ artikul: string; client: string } | null>(null);
  const [quantity, setQuantity] = useState("1");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const stockQuery = useQuery({
    queryKey: ["stock-preview", lookedUp?.artikul, lookedUp?.client],
    queryFn: () => fetchStockPreview(lookedUp!.artikul, lookedUp!.client),
    enabled: lookedUp !== null,
  });

  const addMutation = useMutation({
    mutationFn: () =>
      createResult({ artikul: lookedUp!.artikul, client: lookedUp!.client, quantity: Number(quantity) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["results"] });
      setSuccessMessage(`Added ${quantity} × ${lookedUp!.artikul} for ${lookedUp!.client}`);
      setLookedUp(null);
      setArtikul("");
      setClient("");
      setQuantity("1");
    },
  });

  function handleLookup(event: FormEvent) {
    event.preventDefault();
    setSuccessMessage(null);
    if (artikul.trim() && client.trim()) {
      setLookedUp({ artikul: artikul.trim(), client: client.trim() });
      setQuantity("1");
    }
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
          Article
          <input
            value={artikul}
            onChange={(e) => setArtikul(e.target.value)}
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2"
          />
        </label>
        <label className="flex-1 text-sm text-neutral-600">
          Client
          <input
            value={client}
            onChange={(e) => setClient(e.target.value)}
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2"
          />
        </label>
        <button type="submit" className="rounded border border-neutral-300 px-3 py-2 text-sm">
          Look up stock
        </button>
      </form>

      {successMessage && <p className="mb-4 text-sm text-green-700">{successMessage}</p>}

      {lookedUp && stockQuery.isLoading && <p className="text-neutral-500">Checking stock…</p>}
      {lookedUp && stockQuery.isError && <p className="text-red-600">Failed to check stock.</p>}

      {lookedUp && preview && (
        <div className="max-w-lg rounded border border-neutral-200 p-4">
          <p className="mb-2 font-medium">
            {lookedUp.artikul} → {lookedUp.client}
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
