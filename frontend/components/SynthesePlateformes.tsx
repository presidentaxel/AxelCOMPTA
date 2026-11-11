"use client";

import { useEffect, useState } from "react";

import { lireSynthesePlateformes, type SynthesePlateformes as Synthese } from "@/lib/auth-gestionnaire";
import { resumePlateformes } from "@/lib/plateformes";

/** AXE-819, doc 19 : le gestionnaire voit combien de plateformes le
 * chauffeur a reliées, jamais un montant. */
export function SynthesePlateformes({ dossierId }: { dossierId: string }) {
  const [synthese, setSynthese] = useState<Synthese | null>(null);
  useEffect(() => {
    let actif = true;
    lireSynthesePlateformes(dossierId)
      .then((lue) => {
        if (actif) setSynthese(lue);
      })
      .catch(() => {
        // Non lue : rien d'affiché plutôt qu'un faux « aucune ».
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);
  if (!synthese) return null;
  return <p className="mt-2 text-sm text-subtle">{resumePlateformes(synthese)}</p>;
}
