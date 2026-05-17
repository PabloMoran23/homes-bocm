import type { ReactNode } from "react";

/** Las rutas /madrid/* redirigen en cada page; el layout evita el sub-nav antiguo. */
export default function MadridLayout({ children }: { children: ReactNode }) {
  return children;
}
