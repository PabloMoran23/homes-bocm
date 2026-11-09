import type { Metadata } from "next";
import { Suspense } from "react";
import { redirect } from "next/navigation";
import { BoletinAreaApp } from "@/components/BoletinAreaApp";

export const metadata: Metadata = { title:"Tu zona · Resultado de la consulta", robots:{index:false,follow:true} };
export default async function AreaResultsPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const params = await searchParams;
  if (!(typeof params.q === "string" && params.q.trim()) && !(typeof params.ndp === "string" && params.ndp.trim())) redirect("/boletin");
  return <Suspense fallback={<p className="mx-auto max-w-7xl px-6 py-10 text-sm text-slate-500">Preparando la consulta de tu zona…</p>}><BoletinAreaApp view="results" /></Suspense>;
}
