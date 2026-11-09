"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { CHEMIN_DOUBLE_AUTHENTIFICATION } from "@/lib/mfa-code";
import { cheminDeRetour } from "@/lib/session";

/** L'ancienne adresse. On garde le retour d'origine (la page quittée),
 * pas cette adresse elle-même. */
export default function AncienneAdresseSecurite() {
  const router = useRouter();

  useEffect(() => {
    const retour = cheminDeRetour(window.location.search, "/");
    const params = new URLSearchParams({
      retour: retour === "/securite" || retour.startsWith("/securite?") ? "/" : retour,
    });
    router.replace(`${CHEMIN_DOUBLE_AUTHENTIFICATION}?${params.toString()}`);
  }, [router]);

  return null;
}
