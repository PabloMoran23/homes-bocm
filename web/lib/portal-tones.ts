/** Tonos de etiqueta alineados con el plano (papel, agua, terracota, ocre). */
export const PORTAL_TAG_TONE = {
  teal: "bg-[var(--portal-accent-soft)] text-[var(--portal-accent)] ring-[var(--portal-accent)]/25",
  violet: "bg-[#f0e6e1] text-[#6b534e] ring-[#c07f6c]/35",
  amber: "bg-[#f4e8d2] text-[#8a5a1e] ring-[#d4923a]/40",
  sky: "bg-[#e4ecec] text-[#2a5c60] ring-[#1f4f53]/25",
  slate: "bg-[var(--portal-paper-deep)] text-[var(--portal-ink)]/75 ring-[var(--portal-ink)]/10",
} as const;

export const PORTAL_TAG_TONE_BORDERED = {
  teal: "border-[var(--portal-accent)]/20 bg-[var(--portal-accent-soft)] text-[var(--portal-accent)] ring-[var(--portal-accent)]/10",
  violet: "border-[#c07f6c]/30 bg-[#f0e6e1] text-[#6b534e] ring-[#c07f6c]/10",
  amber: "border-[#d4923a]/35 bg-[#f4e8d2] text-[#8a5a1e] ring-[#d4923a]/10",
  sky: "border-[#1f4f53]/20 bg-[#e4ecec] text-[#2a5c60] ring-[#1f4f53]/10",
  slate: "border-[var(--portal-ink)]/10 bg-[var(--portal-paper)] text-[var(--portal-ink)]/80 ring-[var(--portal-ink)]/5",
} as const;
