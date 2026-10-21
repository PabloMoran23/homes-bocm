"use client";

import dynamic from "next/dynamic";
import { WhenIdle } from "@/components/WhenIdle";

const LandingMapBackground = dynamic(
  () => import("@/components/LandingMapBackground").then((m) => m.LandingMapBackground),
  { ssr: false },
);

export function DeferredLandingMap() {
  return (
    <WhenIdle delayMs={5000}>
      <LandingMapBackground />
    </WhenIdle>
  );
}
