"use client";

import dynamic from "next/dynamic";
import { WhenIdle } from "@/components/WhenIdle";

const LandingAreaMap = dynamic(
  () => import("@/components/LandingAreaMap").then((m) => m.LandingAreaMap),
  { ssr: false },
);

export function DeferredLandingAreaMap() {
  return (
    <WhenIdle delayMs={5000} fallback={<div className="landing-area-map" />}>
      <LandingAreaMap />
    </WhenIdle>
  );
}
