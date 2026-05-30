import Image from "next/image";

type SiteLogoProps = {
  className?: string;
  height?: number;
};

export function SiteLogo({ className = "", height = 24 }: SiteLogoProps) {
  const width = Math.round(height * (866 / 591));

  return (
    <Image
      src="/logo.png"
      alt=""
      width={width}
      height={height}
      className={`shrink-0 ${className}`}
      priority
    />
  );
}
