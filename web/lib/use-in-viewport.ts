"use client";

import { useCallback, useEffect, useState } from "react";

/** Monta contenido pesado solo cuando el contenedor entra en viewport. */
export function useInViewport(options?: IntersectionObserverInit) {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const ref = useCallback((el: HTMLDivElement | null) => setNode(el), []);

  useEffect(() => {
    if (!node || visible) return;

    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "120px 0px", threshold: 0.05, ...options },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [node, visible, options]);

  return { ref, visible };
}
