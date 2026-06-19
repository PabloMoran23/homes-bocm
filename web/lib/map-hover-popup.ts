import L from "leaflet";

const POPUP_CLOSE_DELAY_MS = 240;
const popupHoverBound = new WeakSet<HTMLElement>();

export type MapHoverPopupOptions = {
  className?: string;
  maxWidth?: number;
};

/** Escritorio con ratón: hover. Táctil / móvil: tap. */
export function prefersMapHoverPopup(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

function attachPopupHoverKeepOpen(
  layer: L.Layer,
  cancelClose: () => void,
  scheduleClose: () => void,
) {
  const popup = layer.getPopup();
  const el = popup?.getElement();
  if (!el || popupHoverBound.has(el)) return;
  popupHoverBound.add(el);
  el.addEventListener("mouseenter", cancelClose);
  el.addEventListener("mouseleave", scheduleClose);
}

function stopTouchFromPanningMap(e: L.LeafletEvent) {
  L.DomEvent.stopPropagation(e);
}

/** Popup al pasar el ratón en desktop; en móvil, al pulsar el elemento. */
export function bindMapHoverPopup(
  layer: L.Layer,
  html: string,
  options?: MapHoverPopupOptions,
): void {
  const className = options?.className ?? "homes-map-popup";
  const maxWidth = options?.maxWidth ?? 320;
  const hoverMode = prefersMapHoverPopup();

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

  const openPopup = () => {
    cancelClose();
    layer.openPopup();
    if (hoverMode) {
      attachPopupHoverKeepOpen(layer, cancelClose, scheduleClose);
    }
  };

  // Evita que el mapa interprete el tap como inicio de arrastre.
  layer.on("mousedown", stopTouchFromPanningMap);
  layer.on("touchstart", stopTouchFromPanningMap);

  layer.on("click", (e) => {
    stopTouchFromPanningMap(e);
    openPopup();
  });

  if (!hoverMode) return;

  layer.on("mouseover", openPopup);
  layer.on("mouseout", scheduleClose);
}
