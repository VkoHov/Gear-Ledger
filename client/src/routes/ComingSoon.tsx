export function ComingSoon({ title }: { title: string }) {
  return (
    <div className="rounded-lg border border-dashed border-neutral-300 p-10 text-center text-neutral-500">
      <p className="text-lg font-medium">{title}</p>
      <p className="mt-1 text-sm">Coming in a later milestone.</p>
    </div>
  );
}
