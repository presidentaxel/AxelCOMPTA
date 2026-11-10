"use client";

import { useParams } from "next/navigation";
import { useCallback } from "react";

import { RepriseFec, type ChampsReprise } from "@/components/RepriseFec";
import { analyserFecChauffeur, lireOuvertureChauffeur, reprendreFecChauffeur } from "@/lib/auth-chauffeur";

/** AXE-804 : la société existait avant AxeLCompta ; son dirigeant reprend
 * son bilan d'ouverture depuis le FEC de l'outil précédent. */
export default function OuverturePage() {
  const { dossierId } = useParams<{ dossierId: string }>();
  const lire = useCallback(() => lireOuvertureChauffeur(dossierId), [dossierId]);
  const analyser = useCallback(
    (fichier: File, correspondance: string) => analyserFecChauffeur(dossierId, fichier, correspondance),
    [dossierId],
  );
  const reprendre = useCallback(
    (fichier: File, champs: ChampsReprise) => reprendreFecChauffeur(dossierId, fichier, champs),
    [dossierId],
  );
  return (
    <section aria-labelledby="titre-ouverture">
      <h1 id="titre-ouverture" className="text-xl font-semibold text-ink">
        Reprendre mes comptes
      </h1>
      <RepriseFec lire={lire} analyser={analyser} reprendre={reprendre} />
    </section>
  );
}
