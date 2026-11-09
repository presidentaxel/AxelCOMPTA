"use client";

import { useEffect, useState } from "react";

import { lireIntegrationsEnvoi } from "@/lib/auth-gestionnaire";

/** AXE-808 : les canaux d'envoi branchés (`null` tant que non lus). */
export function useCanauxEnvoi(): string[] | null {
  const [canaux, setCanaux] = useState<string[] | null>(null);
  useEffect(() => {
    let actif = true;
    lireIntegrationsEnvoi()
      .then((lus) => {
        if (actif) setCanaux(Object.keys(lus));
      })
      .catch(() => {
        if (actif) setCanaux([]);
      });
    return () => {
      actif = false;
    };
  }, []);
  return canaux;
}
