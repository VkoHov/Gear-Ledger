import { useRef, useState, type ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCatalogInfo, uploadCatalog } from "../api/catalog";

export function Catalog() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const infoQuery = useQuery({ queryKey: ["catalog-info"], queryFn: fetchCatalogInfo });

  const uploadMutation = useMutation({
    mutationFn: uploadCatalog,
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["catalog-info"] });
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "Upload failed"),
  });

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Catalog</h1>

      {infoQuery.isLoading && <p className="text-neutral-500">Loading…</p>}

      {infoQuery.data && (
        <div className="mb-4 rounded border border-neutral-200 p-4">
          {infoQuery.data.exists ? (
            <>
              <p className="font-medium">{infoQuery.data.filename}</p>
              <p className="text-sm text-neutral-500">
                {infoQuery.data.size ? `${Math.round(infoQuery.data.size / 1024)} KB` : ""}
                {infoQuery.data.modified
                  ? ` · updated ${new Date(infoQuery.data.modified * 1000).toLocaleString()}`
                  : ""}
              </p>
            </>
          ) : (
            <p className="text-neutral-500">No catalog uploaded yet.</p>
          )}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileChange}
        disabled={uploadMutation.isPending}
      />
      {uploadMutation.isPending && <p className="mt-2 text-sm text-neutral-500">Uploading…</p>}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
