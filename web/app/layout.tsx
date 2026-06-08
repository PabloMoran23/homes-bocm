import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@/components/Analytics";
import { NavBar } from "@/components/NavBar";
import { SiteFooter } from "@/components/SiteFooter";
import { TierProvider } from "@/components/TierProvider";
import { isPublicEdition } from "@/lib/edition";
import { DEFAULT_OG_IMAGE, withCanonical, withDefaultOgImage } from "@/lib/seo";
import { getSiteUrl } from "@/lib/site-url";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const isPublic = isPublicEdition();

const siteName = isPublic ? "Homes · Urbanismo Madrid" : "Homes · Urbanismo";
const siteDescription = isPublic
  ? "Mapa unificado de licencias, proyectos de planeamiento y anuncios BOCM en Madrid capital. Explora, abre fichas y consulta estadísticas."
  : "Seguimiento de proyectos urbanísticos cerca de ti: mapa, alertas, estudio por zona y lectura clara. Cruzamos más de 1.000 fuentes para que no tengas que hacerlo tú.";

export const metadata: Metadata = {
  metadataBase: new URL(getSiteUrl()),
  title: {
    default: isPublic ? siteName : "Homes · Urbanismo — proyectos en tu zona",
    template: "%s · Homes Urbanismo",
  },
  description: siteDescription,
  icons: {
    icon: [{ url: "/logo.png", type: "image/png" }],
    apple: [{ url: "/logo-192.png", sizes: "192x192", type: "image/png" }],
  },
  manifest: "/site.webmanifest",
  openGraph: {
    type: "website",
    locale: "es_ES",
    siteName,
    title: siteName,
    description: siteDescription,
  },
  twitter: {
    card: "summary_large_image",
    title: siteName,
    description: siteDescription,
  },
  ...(isPublic
    ? {}
    : {
        robots: { index: false, follow: false },
      }),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="flex min-h-full flex-col bg-[var(--surface)] font-sans text-slate-900 antialiased">
        <Analytics />
        <TierProvider>
          <NavBar />
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
          <SiteFooter />
        </TierProvider>
      </body>
    </html>
  );
}
