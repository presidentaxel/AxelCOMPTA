"use client";

import { useParams } from "next/navigation";
import { useCallback } from "react";

import { RepriseFec, type ChampsReprise } from "@/components/RepriseFec";
import { analyserFecExpert, lireOuvertureExpert, reprendreFecExpert } from "@/lib/auth-gestionnaire";

/** AXE-804 : l'expert-comptable habilité reprend le bilan d'ouverture d'un
 * dossier de sa lettre de mission, sous sa responsabilité (AXE-800). */
export default function OuvertureExpertPage() {
  const { dossierId } = useParams<{ dossierId: string }>();
  const lire = useCallback(() => lireOuvertureExpert(dossierId), [dossierId]);
  const analyser = useCallback(
    (fichier: File, correspondance: string) => analyserFecExpert(dossierId, fichier, correspondance),
    [dossierId],
  );
  const reprendre = useCallback(
    (fichier: File, champs: ChampsReprise) =>
      reprendreFecExpert(dossierId, fichier, { ...champs, motif: champs.motif ?? "" }),
    [dossierId],
  );
  return (
    <section aria-labelledby="titre-ouverture" className="max-w-2xl">
      <h1 id="titre-ouverture" className="text-xl font-semibold text-ink">
        Bilan d&apos;ouverture
      </h1>
      <RepriseFec lire={lire} analyser={analyser} reprendre={reprendre} avecMotif />
    </section>
  );
}
