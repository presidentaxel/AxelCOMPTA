"use client";

// doc 20, doc 19 §5.3 : le chauffeur dépose lui-même sur le guichet INPI.
// Cet écran lui donne les réponses de son dossier et les pièces au nom
// demandé par le portail. La signature qualifiée reste un bouchon (ADR-004).
import { useState } from "react";

import { Aide } from "@/components/Aide";
import { Button } from "@/components/ui/button";
import { ApiError, cheminGreffeInpi } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  signerGreffeInpiChauffeur,
  telechargerAvecAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import type { DossierResume } from "@/lib/types";

import { Badge } from "./Badge";

function messageErreur(exception: unknown, repli: string): string {
  const brut =
    exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
      ? exception.message
      : repli;
  return phrasePourChauffeur(brut);
}

export function GreffeInpiSection({ dossier }: { dossier: DossierResume }) {
  const guide = dossier.guide_greffe;
  const [signe, setSigne] = useState(dossier.greffe_inpi_signe);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function signer() {
    setEnCours(true);
    setErreur(null);
    try {
      await signerGreffeInpiChauffeur(dossier.dossier_id);
      setSigne(true);
    } catch (exception) {
      setErreur(messageErreur(exception, "Échec de la signature."));
    } finally {
      setEnCours(false);
    }
  }

  async function telecharger(chemin: string, nomFichier: string) {
    setErreur(null);
    try {
      await telechargerAvecAuthChauffeur(chemin, nomFichier);
    } catch (exception) {
      setErreur(messageErreur(exception, "Échec du téléchargement."));
    }
  }

  return (
    <section className="mt-10">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-base font-semibold text-ink">
          Dépôt des comptes
          <Aide texte="Le greffe du tribunal de commerce reçoit les comptes de l'année, sur le portail de l'INPI. Rien n'est envoyé depuis ici." />
        </h2>
        {signe ? <Badge variant="validated">Signé</Badge> : <Badge variant="pending">À signer</Badge>}
      </div>
      {guide.depose ? (
        <>
          <p className="mt-1 text-sm text-subtle">
            À reporter sur le portail. Rien n&apos;est envoyé d&apos;ici.
          </p>
          <Button asChild className="mt-4 w-full">
            <a href={guide.lien} target="_blank" rel="noopener noreferrer">
              Ouvrir le portail INPI
            </a>
          </Button>
          <ul className="mt-4">
            {guide.lignes.map((ligne) => (
              <li key={ligne.question} className="border-b border-hairline py-3">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="text-sm text-subtle">{ligne.question}</span>
                  <span className="shrink-0 text-sm font-medium text-ink">{ligne.reponse}</span>
                </div>
                {ligne.detail && <p className="mt-1 text-sm text-subtle">{ligne.detail}</p>}
              </li>
            ))}
          </ul>
          <h3 className="mt-8 text-sm font-medium text-ink">Pièces à joindre</h3>
          <ul>
            {guide.pieces.map((piece) => {
              const document = piece.document;
              return (
                <li key={piece.nom} className="border-b border-hairline py-3">
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="text-sm font-medium text-ink">{piece.nom}</span>
                    {document && (
                      <button
                        type="button"
                        onClick={() =>
                          void telecharger(
                            `/dossiers/${dossier.dossier_id}/${document}`,
                            `${document.replace(".pdf", "")}-${dossier.dossier_id}.pdf`,
                          )
                        }
                        className="shrink-0 text-sm text-primary"
                      >
                        Télécharger
                      </button>
                    )}
                  </div>
                  {piece.detail && <p className="mt-1 text-sm text-subtle">{piece.detail}</p>}
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <p className="mt-2 text-sm text-subtle">Cette forme de société ne dépose pas ses comptes.</p>
      )}
      <button
        type="button"
        onClick={() =>
          void telecharger(cheminGreffeInpi(dossier.dossier_id), `greffe-inpi-${dossier.dossier_id}.pdf`)
        }
        className="mt-4 py-2 text-left text-sm text-primary"
      >
        Télécharger le dossier de synthèse
      </button>
      {!signe && (
        <Button
          type="button"
          variant="secondary"
          className="mt-2 w-full"
          disabled={enCours}
          onClick={() => void signer()}
        >
          {enCours ? "Signature…" : "Signer"}
        </Button>
      )}
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}
