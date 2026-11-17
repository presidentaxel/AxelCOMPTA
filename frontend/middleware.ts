import { NextResponse, type NextRequest } from "next/server";

import { decisionPorte } from "@/lib/porte-dossier";

/** AXE-965. La décision est dans `lib/porte-dossier`, testée sans le serveur. */
export function middleware(request: NextRequest) {
  const decision = decisionPorte(
    request.headers.get("host") ?? "",
    request.nextUrl.pathname,
    request.nextUrl.search,
  );
  if (decision.action === "continuer") return NextResponse.next();
  const cible = new URL(decision.url, request.url);
  // Caddy termine le TLS. Le lien renvoyé au navigateur reste en https.
  if (request.headers.get("x-forwarded-proto") === "https") cible.protocol = "https:";
  return NextResponse.redirect(cible, 308);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
