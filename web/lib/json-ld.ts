import { isPublicEdition } from "@/lib/edition";
import type { SeoFaqItem } from "@/lib/seo-faq-content";
import { getSiteUrl } from "@/lib/site-url";
import type { MadridDashboardStats } from "@/lib/types";

const SCHEMA_CONTEXT = "https://schema.org";

export type JsonLdNode = Record<string, unknown>;

export function absoluteSiteUrl(path = "/"): string {
  const base = getSiteUrl().replace(/\/$/, "");
  if (!path || path === "/") return `${base}/`;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function siteName(): string {
  return isPublicEdition() ? "Homes · Urbanismo Madrid" : "Homes · Urbanismo";
}

function siteDescription(): string {
  return isPublicEdition()
    ? "Qué obras y planes hay en Madrid capital. Mapa, actividad cerca de tu calle y dashboard por barrios."
    : "Seguimiento de actividad urbanística cerca de ti: mapa, alertas, estudio por zona y lectura clara.";
}

export function organizationJsonLd(): JsonLdNode {
  const url = absoluteSiteUrl("/");
  return {
    "@type": "Organization",
    "@id": `${url}#organization`,
    name: siteName(),
    url,
    logo: absoluteSiteUrl("/logo.png"),
    description: siteDescription(),
  };
}

export function websiteJsonLd(): JsonLdNode {
  const url = absoluteSiteUrl("/");
  return {
    "@type": "WebSite",
    "@id": `${url}#website`,
    name: siteName(),
    url,
    description: siteDescription(),
    publisher: { "@id": `${url}#organization` },
    inLanguage: "es-ES",
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${absoluteSiteUrl("/boletin")}?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function globalSiteJsonLd(): JsonLdNode {
  return {
    "@context": SCHEMA_CONTEXT,
    "@graph": [organizationJsonLd(), websiteJsonLd()],
  };
}

export function faqPageJsonLd(path: string, items: readonly SeoFaqItem[]): JsonLdNode {
  return {
    "@context": SCHEMA_CONTEXT,
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.a,
      },
    })),
    url: absoluteSiteUrl(path),
  };
}

export function breadcrumbJsonLd(
  path: string,
  crumbs: readonly { name: string; path?: string }[],
): JsonLdNode {
  return {
    "@context": SCHEMA_CONTEXT,
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      ...(crumb.path ? { item: absoluteSiteUrl(crumb.path) } : {}),
    })),
    url: absoluteSiteUrl(path),
  };
}

export function proyectoBreadcrumbJsonLd(id: string, title: string): JsonLdNode {
  const path = `/proyecto/${encodeURIComponent(id)}`;
  return breadcrumbJsonLd(path, [
    { name: "Inicio", path: "/" },
    { name: "Mapa Madrid", path: "/explore" },
    { name: title.length > 120 ? `${title.slice(0, 117)}…` : title },
  ]);
}

export function madridDatasetJsonLd(stats: MadridDashboardStats): JsonLdNode {
  const path = "/madrid/estadisticas";
  const url = absoluteSiteUrl(path);
  const licencias = stats.licencias?.totalRows;
  const sigma = stats.sigma?.total;

  const parts = [
    licencias != null ? `${licencias.toLocaleString("es-ES")} licencias urbanísticas` : null,
    sigma != null ? `${sigma.toLocaleString("es-ES")} expedientes SIGMA` : null,
  ].filter(Boolean);

  return {
    "@context": SCHEMA_CONTEXT,
    "@type": "Dataset",
    name: "Estadísticas de licencias urbanísticas y planeamiento en Madrid",
    description:
      "Agregados de licencias de obra, expedientes SIGMA y métricas de planeamiento del Ayuntamiento de Madrid capital, actualizados semanalmente.",
    url,
    inLanguage: "es-ES",
    creator: { "@id": `${absoluteSiteUrl("/")}#organization` },
    dateModified: stats.generatedAt,
    keywords: [
      "licencias urbanísticas Madrid",
      "planeamiento Madrid",
      "SIGMA Madrid",
      "estadísticas urbanismo",
    ],
    spatialCoverage: {
      "@type": "Place",
      name: "Madrid capital",
      address: {
        "@type": "PostalAddress",
        addressLocality: "Madrid",
        addressCountry: "ES",
      },
    },
    ...(parts.length
      ? {
          variableMeasured: parts,
        }
      : {}),
  };
}
