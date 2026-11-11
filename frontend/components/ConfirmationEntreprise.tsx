"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  confirmerConfigurationChauffeur,
  fetchAvecAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { aConfirmer, libelleForme, phraseIdentiteManquante } from "@/lib/confirmation-configuration";
import { libelleImposition, libelleRegimeTva } from "@/lib/dossier-libelles";
import { formatDate } from "@/lib/format";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import type { ConfigurationDossier } from "@/lib/types";

/** AXE-730 : « Vérifiez votre entreprise ». Le chauffeur confirme ce que
 * Sirene a proposé (forme, premier exercice) ; tant qu'il ne l'a pas fait,
 * la clôture et la liasse sont refusées. Rien ne s'affiche s'il n'y a rien
 * à confirmer ni à saisir. */
export function ConfirmationEntreprise({ dossierId }: { dossierId: string }) {
  const [configuration, setConfiguration] = useState<ConfigurationDossier | null>(null);
  const [forme, setForme] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    fetchAvecAuthChauffeur<ConfigurationDossier>(`/dossiers/${dossierId}/configuration`)
      .then((lue) => {
        if (actif) setConfiguration(lue);
      })
      .catch(() => {
        // Écran secondaire : la clôture dira elle-même ce qui bloque.
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);

  if (!configuration) return null;
  const manque = phraseIdentiteManquante(configuration.identite_manquante);
  const lienSociete = manque && <LienMaSociete dossierId={dossierId} phrase={manque} />;
  if (!aConfirmer(configuration)) {
    return lienSociete || null;
  }
  const choix = configuration.formes_proposees;
  const formeChoisie = choix.length === 1 ? choix[0] : forme;

  async function confirmer() {
    if (!formeChoisie || enCours) return;
    setEnCours(true);
    setErreur(null);
    try {
      setConfiguration(await confirmerConfigurationChauffeur(dossierId, formeChoisie));
    } catch (exception) {
      const message =
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "La confirmation n'a pas pu être enregistrée.";
      setErreur(phrasePourChauffeur(message));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section aria-labelledby="titre-entreprise" className="mt-4 rounded-md border border-warning/40 bg-pending-subtle p-3">
      <h2 id="titre-entreprise" className="text-sm font-medium text-ink">
        Vérifiez votre entreprise
      </h2>
      <p className="mt-1 text-sm text-subtle">Votre bilan ne peut pas être préparé avant.</p>
      {choix.length > 1 && (
        <fieldset className="mt-3">
          <legend className="text-sm text-ink">Votre société est une :</legend>
          <div className="mt-2 flex flex-col gap-2">
            {choix.map((code) => (
              <Button
                key={code}
                type="button"
                variant={forme === code ? "primary" : "secondary"}
                aria-pressed={forme === code}
                className="h-auto min-h-11 w-full whitespace-normal! px-3"
                disabled={enCours}
                onClick={() => setForme(code)}
              >
                {libelleForme(code)}
              </Button>
            ))}
          </div>
        </fieldset>
      )}
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        {choix.length === 1 && (
          <>
            <dt className="text-subtle">Forme</dt>
            <dd className="text-ink">{libelleForme(choix[0])}</dd>
          </>
        )}
        <dt className="text-subtle">Impôt</dt>
        <dd className="text-ink">{libelleImposition(configuration.regime_imposition)}</dd>
        <dt className="text-subtle">TVA</dt>
        <dd className="text-ink">{libelleRegimeTva(configuration.regime_tva)}</dd>
        <dt className="text-subtle">Exercice</dt>
        <dd className="text-ink">
          du {formatDate(configuration.exercice_debut)} au {formatDate(configuration.exercice_fin)}
        </dd>
      </dl>
      <Button type="button" className="mt-3 h-11 w-full" disabled={!formeChoisie || enCours} onClick={confirmer}>
        Oui, c&apos;est bien mon entreprise
      </Button>
      <p className="mt-2 text-xs text-subtle">Une erreur ? Prévenez votre gestionnaire avant de confirmer.</p>
      {lienSociete}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </section>
  );
}

/** AXE-846 : siège, capital et associés se saisissent sur « Ma société ». */
function LienMaSociete({ dossierId, phrase }: { dossierId: string; phrase: string }) {
  return (
    <p className="mt-4 text-sm text-ink">
      {phrase}{" "}
      <Link href={`/chauffeur/${dossierId}/entreprise`} className="inline-flex min-h-11 items-center font-medium text-primary">
        Renseigner ma société
      </Link>
    </p>
  );
}
