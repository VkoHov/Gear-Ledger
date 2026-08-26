import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { generateInvoice } from "../api/reports";

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function Invoice() {
  const [weightPrice, setWeightPrice] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (price: number) => generateInvoice(price),
    onSuccess: (blob) => {
      setError(null);
      const filename = `invoice_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.xlsx`;
      downloadBlob(blob, filename);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "Invoice generation failed"),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const price = Number(weightPrice);
    if (Number.isNaN(price)) {
      setError("Weight price must be a number");
      return;
    }
    mutation.mutate(price);
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Invoice</h1>
      <form onSubmit={handleSubmit} className="flex max-w-sm flex-col gap-3">
        <label className="text-sm text-neutral-600">
          Weight price
          <input
            type="number"
            step="any"
            min={0}
            value={weightPrice}
            onChange={(e) => setWeightPrice(e.target.value)}
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2"
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded bg-neutral-900 px-3 py-2 text-white disabled:opacity-50"
        >
          {mutation.isPending ? "Generating…" : "Generate invoice"}
        </button>
      </form>
    </div>
  );
}
