import { NextResponse } from "next/server";
import { suggestAddresses } from "@/lib/cartociudad";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams.get("q")?.trim() || "";
  if (q.length < 3 || q.length > 200) return NextResponse.json({ error: "Escribe una calle y un municipio" }, { status: 400 });
  try {
    return NextResponse.json(await suggestAddresses(q));
  } catch {
    return NextResponse.json({ error: "No se pudieron cargar las direcciones. Vuelve a intentarlo." }, { status: 502 });
  }
}
