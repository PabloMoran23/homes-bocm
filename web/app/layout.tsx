import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { NavBar } from "@/components/NavBar";
import { SiteFooter } from "@/components/SiteFooter";
import { TierProvider } from "@/components/TierProvider";
import { isPublicEdition } from "@/lib/edition";
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

export const metadata: Metadata = {
  title: {
    default: isPublic
      ? "Homes · Urbanismo Madrid"
      : "Homes · Urbanismo — proyectos en tu zona",
    template: "%s · Homes Urbanismo",
  },
  description: isPublic
    ? "Mapa unificado de licencias, planeamiento SIGMA y anuncios BOCM en Madrid capital. Explora, abre fichas y consulta estadísticas."
    : "Seguimiento de proyectos urbanísticos cerca de ti: mapa, alertas, estudio por zona y lectura clara. Cruzamos más de 1.000 fuentes para que no tengas que hacerlo tú.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="flex min-h-full flex-col bg-[var(--surface)] font-sans text-slate-900 antialiased">
        <TierProvider>
          <NavBar />
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
          <SiteFooter />
        </TierProvider>
      </body>
    </html>
  );
}
