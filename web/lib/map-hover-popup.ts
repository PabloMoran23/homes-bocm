import L from "leaflet";

const POPUP_CLOSE_DELAY_MS = 240;
const popupHoverBound = new WeakSet<HTMLElement>();

export type MapHoverPopupOptions = {
  className?: string;
  maxWidth?: number;
};

function canUseHoverPopup(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

function attachPopupHover(layer: L.Layer, cancelClose: () => void, scheduleClose: () => void) {
  const popup = layer.getPopup();
  const el = popup?.getElement();
  if (!el || popupHoverBound.has(el)) return;
  popupHoverBound.add(el);
  el.addEventListener("mouseenter", cancelClose);
  el.addEventListener("mouseleave", scheduleClose);
}

/** Popup al pasar el ratón; en táctil, clic abre/cierra. Sin navegación directa al feature. */
export function bindMapHoverPopup(
  layer: L.Layer,
  html: string,
  options?: MapHoverPopupOptions,
): void {
  const className = options?.className ?? "homes-map-popup";
  const maxWidth = options?.maxWidth ?? 320;

  layer.bindPopup(html, {
    className,
    maxWidth,
    closeButton: true,
    autoPan: true,
  });

  let closeTimer: ReturnType<typeof setTimeout> | null = null;

  const cancelClose = () => {
    if (closeTimer) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
  };

  const scheduleClose = () => {
    cancelClose();
    closeTimer = setTimeout(() => {
      layer.closePopup();
    }, POPUP_CLOSE_DELAY_MS);
  };

  layer.on("click", (e) => {
    L.DomEvent.stopPropagation(e);
    if (canUseHoverPopup()) {
      layer.openPopup();
      attachPopupHover(layer, cancelClose, scheduleClose);
      return;
    }
    layer.togglePopup();
    attachPopupHover(layer, cancelClose, scheduleClose);
  });

  if (!canUseHoverPopup()) return;

  layer.on("mouseover", () => {
    cancelClose();
    layer.openPopup();
    attachPopupHover(layer, cancelClose, scheduleClose);
  });

  layer.on("mouseout", scheduleClose);
}
