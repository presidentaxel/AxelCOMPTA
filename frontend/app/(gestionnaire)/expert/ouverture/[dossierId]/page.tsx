"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { RepriseFec, type ChampsReprise, type FecPropose } from "@/components/RepriseFec";
import {
  analyserBalanceExpert,
  analyserFecExpert,
  lireFecDeLaFicheExpert,
  lireOuvertureExpert,
  reprendreBalanceExpert,
  reprendreFecExpert,
  telechargerDocumentImport,
} from "@/lib/auth-gestionnaire";

/** AXE-992 : le fichier vide qui représente la balance de la fiche ; le
 * serveur relit la balance elle-même par son identifiant. */
const BALANCE = "Balance lue sur la fiche d'import";

function dateFr(iso: string): string {
  const [annee, mois, jour] = iso.split("-");
  return `${jour}/${mois}/${annee}`;
}

/** AXE-804 : l'expert-comptable habilité reprend le bilan d'ouverture d'un
 * dossier de sa lettre de mission, sous sa responsabilité (AXE-800).
 * AXE-942 : le FEC déposé sur la fiche d'import est proposé d'abord. */
export default function OuvertureExpertPage() {
  const { dossierId } = useParams<{ dossierId: string }>();
  const [propose, setPropose] = useState<FecPropose | null>(null);
  const [balanceId, setBalanceId] = useState<string | null>(null);
  const lire = useCallback(() => lireOuvertureExpert(dossierId), [dossierId]);
  const analyser = useCallback(
    (fichier: File, correspondance: string) =>
      fichier.name === BALANCE && balanceId
        ? analyserBalanceExpert(dossierId, balanceId, correspondance)
        : analyserFecExpert(dossierId, fichier, correspondance),
    [dossierId, balanceId],
  );
  const reprendre = useCallback(
    (fichier: File, champs: ChampsReprise) => {
      const complets = { ...champs, motif: champs.motif ?? "" };
      return fichier.name === BALANCE && balanceId
        ? reprendreBalanceExpert(dossierId, balanceId, complets)
        : reprendreFecExpert(dossierId, fichier, complets);
    },
    [dossierId, balanceId],
  );

  useEffect(() => {
    let actif = true;
    lireFecDeLaFicheExpert(dossierId)
      .then((fec) => {
        if (!actif) return;
        if (!fec.trouve && fec.balance_document_id && fec.balance_au) {
          setBalanceId(fec.balance_document_id);
          setPropose({
            libelle: `La balance au ${dateFr(fec.balance_au)}`,
            phrase:
              `Pas de FEC sur la fiche d'import : la balance au ${dateFr(fec.balance_au)}, ` +
              "lue par l'OCR, peut servir de bilan d'ouverture.",
            bouton: "Utiliser cette balance",
            deficits: fec.deficits,
            charger: async () => new File([], BALANCE),
          });
          return;
        }
        if (!fec.trouve || !fec.fiche_id || !fec.document_id) return;
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
