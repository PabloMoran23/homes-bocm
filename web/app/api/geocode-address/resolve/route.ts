import { NextResponse } from "next/server";
import { resolveAddress } from "@/lib/cartociudad";

export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const id = params.get("id") || "";
  const type = params.get("type");
  if (!/^[\w.-]{1,120}$/.test(id) || (type !== "portal" && type !== "callejero")) {
    return NextResponse.json({ error: "Selecciona una dirección" }, { status: 400 });
  }
  try {
    return NextResponse.json(await resolveAddress(id, type));
  } catch {
    return NextResponse.json({ error: "No se pudo localizar la dirección. Vuelve a seleccionarla." }, { status: 502 });
  }
}
