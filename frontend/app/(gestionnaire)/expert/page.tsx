"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import {
  ErreurAuthGestionnaire,
  imputerExpert,
  lireFileExpert,
} from "@/lib/auth-gestionnaire";
import { remplacerSujetsDuDossier } from "@/lib/file-expert";
import { formatMontant } from "@/lib/format";
import type { FileExpert, SujetExpert } from "@/lib/types";

const PAGE = 50;

const COTE: Record<SujetExpert["cote"], string> = {
  chauffeur: "Chauffeur",
  gestionnaire: "Gestionnaire",
};
const NATURE: Record<SujetExpert["nature"], string> = {
  a_trancher: "À trancher",
  ticket: "Ticket",
  anomalie: "Anomalie",
};

/** File à part du portefeuille : une page de lignes, filtrable, avec un
 * seul sélecteur de compte pour toute la page. */
export default function ModeExpertPage() {
  const router = useRouter();
  const [file, setFile] = useState<FileExpert | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [chargement, setChargement] = useState(true);
  const [compte, setCompte] = useState("");
  const [enCours, setEnCours] = useState<string | null>(null);
  const [entreprise, setEntreprise] = useState("toutes");
  const [nature, setNature] = useState("toutes");
  const [visible, setVisible] = useState(PAGE);

  const charger = useCallback(() => {
    lireFileExpert()
      .then((donnees) => {
        setFile(donnees);
        setErreur(null);
      })
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else {
          setFile(null);
          setErreur("Impossible de charger la file.");
        }
      })
      .finally(() => setChargement(false));
  }, [router]);

  useEffect(charger, [charger]);

  const entreprises = useMemo(() => {
    const noms = new Map<string, string>();
    for (const sujet of file?.sujets ?? []) noms.set(sujet.dossier_id, sujet.dossier_nom);
    return [...noms.entries()].sort((a, b) => a[1].localeCompare(b[1], "fr"));
  }, [file]);

  const filtres = useMemo(() => {
    return (file?.sujets ?? []).filter((sujet) => {
      if (entreprise !== "toutes" && sujet.dossier_id !== entreprise) return false;
      if (nature !== "toutes" && sujet.nature !== nature) return false;
      return true;
    });
  }, [entreprise, file, nature]);

  const page = filtres.slice(0, visible);

  async function imputer(sujet: SujetExpert) {
    if (!compte || !sujet.ecriture_id) return;
    setEnCours(sujet.id);
    setErreur(null);
    try {
      const dossierMisAJour = await imputerExpert(sujet.dossier_id, sujet.ecriture_id, compte);
      setFile((actuelle) =>
        actuelle && {
          ...actuelle,
          sujets: remplacerSujetsDuDossier(actuelle.sujets, sujet.dossier_id, dossierMisAJour),
        },
      );
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec de l'imputation.");
    } finally {
      setEnCours(null);
    }
  }

  function changerFiltre(suivant: "entreprise" | "nature", valeur: string) {
    setVisible(PAGE);
    if (suivant === "entreprise") setEntreprise(valeur);
    else setNature(valeur);
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Mode expert</h1>
      <p className="mt-2 text-sm text-subtle">
        Tout ce qui reste à traiter, entreprises et dossiers confondus. Le portefeuille
        des entreprises ne change pas.
      </p>
      {erreur && (
        <div className="mt-6 flex items-center gap-3">
          <p className="text-sm text-danger">{erreur}</p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              setChargement(true);
              charger();
            }}
          >
            Réessayer
          </Button>
        </div>
      )}
      {chargement && !file && (
        <div className="mt-8 space-y-3" aria-busy="true" aria-label="Chargement de la file">
          <Squelette className="h-10 w-full" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
        </div>
      )}
      {file && (
        <>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <label className="text-sm text-subtle">
              Entreprise
              <select
                value={entreprise}
                onChange={(evenement) => changerFiltre("entreprise", evenement.target.value)}
                className="ml-2 h-9 rounded-md border border-border bg-canvas px-3 text-sm text-ink"
              >
                <option value="toutes">Toutes</option>
                {entreprises.map(([id, nom]) => (
                  <option key={id} value={id}>
                    {nom}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-subtle">
              Nature
              <select
                value={nature}
                onChange={(evenement) => changerFiltre("nature", evenement.target.value)}
                className="ml-2 h-9 rounded-md border border-border bg-canvas px-3 text-sm text-ink"
              >
                <option value="toutes">Toutes</option>
                {(Object.keys(NATURE) as SujetExpert["nature"][]).map((id) => (
                  <option key={id} value={id}>
                    {NATURE[id]}
                  </option>
                ))}
              </select>
            </label>
            <p className="text-sm text-subtle">
              {page.length} sur {filtres.length}
              {filtres.length !== file.sujets.length ? ` (${file.sujets.length} au total)` : ""}
            </p>
          </div>
          {filtres.length > 0 && (
            <label className="mt-4 flex items-center gap-2 text-sm text-ink">
              Compte pour les lignes affichées
              <select
                aria-label="Compte partagé"
                value={compte}
                onChange={(evenement) => setCompte(evenement.target.value)}
                className="h-9 min-w-56 rounded-md border border-border bg-canvas px-3 text-sm text-ink"
              >
                <option value="">Compte</option>
                {file.comptes.map((choix) => (
                  <option key={choix.compte} value={choix.compte}>
                    {choix.compte} — {choix.libelle}
                  </option>
                ))}
              </select>
            </label>
          )}
          {filtres.length === 0 && (
            <p className="mt-8 text-sm text-subtle">
              {file.sujets.length === 0 ? "Rien en attente." : "Aucun sujet pour ce filtre."}
            </p>
          )}
          <ul className="mt-4">
            {page.map((sujet) => (
              <li key={sujet.id} className="border-b border-hairline py-3">
                <div className="flex items-baseline justify-between gap-4">
                  <p className="min-w-0">
                    <span className="block truncate text-base font-semibold text-ink">{sujet.libelle}</span>
                    <span className="mt-0.5 block text-sm text-subtle">
                      {sujet.dossier_nom} · {COTE[sujet.cote]} · {NATURE[sujet.nature]}
                    </span>
                    <span className="mt-0.5 block text-sm text-subtle">{sujet.detail}</span>
                  </p>
                  {sujet.montant_cts !== null && (
                    <span
                      className={`shrink-0 text-base font-semibold tabular-nums ${
                        sujet.montant_cts < 0 ? "text-amount-negative" : "text-amount-positive"
                      }`}
                    >
                      {formatMontant(sujet.montant_cts)}
                    </span>
                  )}
                </div>
                {sujet.imputable && sujet.ecriture_id && (
                  <div className="mt-3">
                    <Button
                      type="button"
                      size="sm"
                      disabled={!compte || enCours === sujet.id}
                      onClick={() => void imputer(sujet)}
                    >
                      Imputer
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {visible < filtres.length && (
            <Button
              type="button"
              variant="secondary"
              className="mt-4"
              onClick={() => setVisible((actuel) => actuel + PAGE)}
            >
              Voir plus
            </Button>
          )}
        </>
      )}
    </div>
  );
}
