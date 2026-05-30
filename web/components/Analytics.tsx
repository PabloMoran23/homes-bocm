import { Analytics as VercelAnalytics } from "@vercel/analytics/next";
import { isPublicEdition } from "@/lib/edition";

/** Vercel Web Analytics (pageviews). Activar en Vercel → Project → Analytics. */
export function Analytics() {
  if (!isPublicEdition()) return null;
  return <VercelAnalytics />;
}
