export function escapeMapPopupHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function escapeMapPopupAttr(s: string): string {
  return escapeMapPopupHtml(s).replace(/'/g, "&#39;");
}

export function mapPopupLinkHtml(href: string, label: string): string {
  return (
    `<a href="${escapeMapPopupAttr(href)}" ` +
    `style="display:inline-block;margin-top:8px;color:#0f766e;font-weight:700;font-size:13px;text-decoration:none">` +
    `${escapeMapPopupHtml(label)} →</a>`
  );
}

export function mapPopupMetaLine(label: string, value: string): string {
  return `<div style="margin-top:4px;font-size:12px;color:#475569"><span style="color:#64748b">${escapeMapPopupHtml(label)}:</span> ${escapeMapPopupHtml(value)}</div>`;
}
