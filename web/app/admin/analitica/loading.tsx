export default function AnalyticsLoading() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="h-8 w-40 animate-pulse rounded-lg bg-white/80" />
      <div className="mt-4 h-28 animate-pulse rounded-2xl bg-white/80" />
      <div className="mt-4 grid grid-cols-2 gap-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <div key={index} className="h-28 animate-pulse rounded-2xl bg-white/80" />
        ))}
      </div>
    </div>
  );
}
