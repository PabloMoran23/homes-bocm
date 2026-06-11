import type { ReactNode } from "react";

type FaqItem = { q: string; a: string };

export function SeoFaq({ items }: { items: FaqItem[] }) {
  return (
    <dl className="mt-4 space-y-4">
      {items.map((item) => (
        <div key={item.q}>
          <dt className="text-sm font-semibold text-slate-800">{item.q}</dt>
          <dd className="mt-1 text-sm leading-relaxed text-slate-600">{item.a}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SeoDetailsBlock({
  summary,
  children,
  className = "",
}: {
  summary: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <details
      className={`group border-t border-slate-200/80 bg-slate-50/95 ${className}`.trim()}
    >
      <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-slate-600 marker:content-none sm:px-6 [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-2">
          <span
            className="text-[10px] text-slate-400 transition group-open:rotate-90"
            aria-hidden
          >
            ▶
          </span>
          {summary}
        </span>
      </summary>
      <div className="border-t border-slate-100 px-4 pb-5 pt-3 sm:px-6">{children}</div>
    </details>
  );
}
