/** Correo de contacto público (Hostinger / dominio propio). */
export const SITE_CONTACT_EMAIL = "info@homes-urbanismo.es";

export const SITE_CONTACT_LABEL = "Homes · Urbanismo Madrid";

export function siteContactMailto(subject?: string): string {
  const base = `mailto:${SITE_CONTACT_EMAIL}`;
  if (!subject) return base;
  return `${base}?subject=${encodeURIComponent(subject)}`;
}
