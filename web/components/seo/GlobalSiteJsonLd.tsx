import { JsonLd } from "@/components/seo/JsonLd";
import { isPublicEdition } from "@/lib/edition";
import { globalSiteJsonLd } from "@/lib/json-ld";

/** Organization + WebSite en todas las páginas públicas indexables. */
export function GlobalSiteJsonLd() {
  if (!isPublicEdition()) return null;
  return <JsonLd data={globalSiteJsonLd()} />;
}
