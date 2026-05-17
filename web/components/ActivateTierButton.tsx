"use client";

import { useRouter } from "next/navigation";
import { useTier } from "./TierProvider";
import type { TierId } from "@/lib/tiers";

export function ActivateTierButton({
  tier,
  children,
  className,
}: {
  tier: TierId;
  children: React.ReactNode;
  className?: string;
}) {
  const { setTier } = useTier();
  const router = useRouter();

  return (
    <button
      type="button"
      className={className}
      onClick={() => {
        setTier(tier);
        router.push("/explore");
      }}
    >
      {children}
    </button>
  );
}
