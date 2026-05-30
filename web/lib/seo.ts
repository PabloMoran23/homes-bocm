import type { Metadata } from "next";

/** Path relativo; `metadataBase` resuelve la URL absoluta. */
export function withCanonical(path: string, metadata: Metadata = {}): Metadata {
  return {
    ...metadata,
    alternates: {
      ...metadata.alternates,
      canonical: path,
    },
    openGraph: {
      ...metadata.openGraph,
      url: path,
    },
  };
}

/** Imagen OG por defecto (generada en `app/opengraph-image.tsx`). */
export const DEFAULT_OG_IMAGE = {
  url: "/opengraph-image",
  width: 1200,
  height: 630,
  alt: "Homes · Urbanismo Madrid",
} as const;

export function withDefaultOgImage(metadata: Metadata = {}): Metadata {
  const existing = metadata.openGraph?.images;
  const images = existing ?? [DEFAULT_OG_IMAGE];
  return {
    ...metadata,
    openGraph: {
      ...metadata.openGraph,
      images,
    },
    twitter: {
      ...metadata.twitter,
      images: metadata.twitter?.images ?? [DEFAULT_OG_IMAGE.url],
    },
  };
}
