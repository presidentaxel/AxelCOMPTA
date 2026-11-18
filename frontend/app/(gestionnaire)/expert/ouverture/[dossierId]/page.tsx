"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { RepriseFec, type ChampsReprise, type FecPropose } from "@/components/RepriseFec";
import {
  analyserFecExpert,
  lireFecDeLaFicheExpert,
  lireOuvertureExpert,
  reprendreFecExpert,
  telechargerDocumentImport,
} from "@/lib/auth-gestionnaire";

/** AXE-804 : l'expert-comptable habilité reprend le bilan d'ouverture d'un
 * dossier de sa lettre de mission, sous sa responsabilité (AXE-800).
 * AXE-942 : le FEC déposé sur la fiche d'import est proposé d'abord. */
export default function OuvertureExpertPage() {
  const { dossierId } = useParams<{ dossierId: string }>();
  const [propose, setPropose] = useState<FecPropose | null>(null);
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

  useEffect(() => {
    let actif = true;
    lireFecDeLaFicheExpert(dossierId)
      .then((fec) => {
        if (!actif || !fec.trouve || !fec.fiche_id || !fec.document_id) return;
        const { fiche_id, document_id } = fec;
        const nom = fec.nom_fichier ?? "FEC.txt";
        setPropose({
          libelle: fec.exercice ? `Le FEC ${fec.exercice}` : "Un FEC",
          deficits: fec.deficits,
          charger: async () => new File([await telechargerDocumentImport(fiche_id, document_id)], nom),
        });
      })
      .catch(() => undefined); // sans fiche lisible, le dépôt à la main reste
    return () => {
      actif = false;
    };
  }, [dossierId]);

  return (
    <section aria-labelledby="titre-ouverture" className="max-w-2xl">
      <h1 id="titre-ouverture" className="text-xl font-semibold text-ink">
        Bilan d&apos;ouverture
      </h1>
      <RepriseFec lire={lire} analyser={analyser} reprendre={reprendre} avecMotif propose={propose} />
    </section>
  );
}
