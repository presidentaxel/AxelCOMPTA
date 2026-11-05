"use client";

// doc 17 §9 Semaine 4 : compte de résultat + bilan simplifié + exports de
// clôture. **Déplacé le 2026-09-11** (doc 19 §2.1/§5.3) : sur la fiche
// dossier indiv, pas gestionnaire — le gestionnaire n'a plus de fiche
// dossier détaillée du tout, seulement l'agrégat du dashboard.
//
// **Boutons plutôt que `<a href>` depuis le 2026-09-11** (doc 19 §8bis) :
// ces routes exigent maintenant un jeton indiv — un lien direct ne peut
// pas porter l'en-tête `Authorization` et échouerait en 401.
// `telechargerAvecAuthChauffeur` fait le fetch authentifié puis déclenche
// l'enregistrement.
import { Download } from "lucide-react";
import { useState } from "react";

import { Aide } from "@/components/Aide";
import { Dialogue } from "@/components/Dialogue";
import { ResultatACeJour } from "@/components/ResultatACeJour";
import { Button } from "@/components/ui/button";
import { cheminTelechargementCloture } from "@/lib/api";
import { ErreurAuthChauffeur, telechargerAvecAuthChauffeur } from "@/lib/auth-chauffeur";
import { phraseOperationsRestantes } from "@/lib/etapes-exercice";
import { formatMontant } from "@/lib/format";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import type { DocumentCloture, DossierResume } from "@/lib/types";

const LIASSE: DocumentCloture = "liasse-fiscale.pdf";

type Piece = {
  document: DocumentCloture;
  label: string;
  detail: string;
  aide: string;
};

const AIDE_OPERATIONS =
  "Le grand livre : le détail de chaque opération, une par une.";
const AIDE_TOTAUX =
  "La balance : le total de ce qui est entré et de ce qui est sorti, regroupé par type.";

/** Pièces à emporter pour les impôts. Pas une télédéclaration : rien n'est
 * envoyé à l'administration depuis cet écran. */
const PIECES: Piece[] = [
  // AXE-422 : on garde le .txt légal (A.47 A-1). Pas de PDF : ce n'est pas
  // le format qu'un contrôle demande.
  {
    document: "fec.txt",
    label: "Fichier pour un contrôle",
    detail: "Texte",
    aide: "Le FEC (fichier des écritures comptables) : la liste de chaque opération, au format que l'administration demande.",
  },
  {
    document: "grand-livre.pdf",
    label: "Chaque opération",
    detail: "PDF",
    aide: AIDE_OPERATIONS,
  },
  { document: "balance.pdf", label: "Totaux par type", detail: "PDF", aide: AIDE_TOTAUX },
  {
    document: "liasse.pdf",
    label: "Lecture courte",
    detail: "PDF",
    aide: "Une page qui résume ce qui vous reste après charges, plus simple que le dossier fiscal complet.",
  },
  {
    document: "grand-livre.csv",
    label: "Chaque opération",
    detail: "Tableur",
    aide: AIDE_OPERATIONS,
  },
  { document: "balance.csv", label: "Totaux par type", detail: "Tableur", aide: AIDE_TOTAUX },
];

/** 2065 à l'impôt sur les sociétés, 2031 à l'impôt sur le revenu. */
function pieceDeclaration(dossier: DossierResume): Piece {
  const numero = dossier.declaration_resultat;
  const societe = numero === "2065";
  return {
    document: `cerfa-${numero}.pdf` as DocumentCloture,
    label: "Déclaration de résultat",
    detail: "PDF",
    aide: societe
      ? "Le formulaire 2065 : la première page du dossier fiscal (la liasse) pour une société à l'impôt sur les sociétés."
      : "Le formulaire 2031 : la première page du dossier fiscal (la liasse) pour une société à l'impôt sur le revenu.",
  };
}

function texteDocuments(operationsRestantes: number, comptesClos: boolean): string {
  if (operationsRestantes > 0) {
    return phraseOperationsRestantes(operationsRestantes);
  }
  const etat = comptesClos ? "Les comptes sont clôturés." : "Les comptes ne sont pas clôturés.";
  const suite = comptesClos
    ? "À télécharger et à conserver."
    : "La liasse définitive sera disponible une fois l'exercice clos.";
  return `${etat} ${suite} La déclaration n'est pas envoyée d'ici.`;
}

export function ChiffresExercice({ dossier }: { dossier: DossierResume }) {
  return (
    <section>
      <ResultatACeJour dossier={dossier} />
      <dl className="mt-4 space-y-2 text-sm">
        <Ligne
          label="Ce que vous avez encaissé"
          cents={dossier.ca_ht_cts}
          aide="Hors taxes : le chiffre d'affaires (CA HT), avant la taxe sur les courses."
        />
        <Ligne label="Ce que vous avez dépensé" cents={dossier.charges_cts} />
        <Ligne
          label="En banque"
          cents={dossier.tresorerie_cts}
          aide="La trésorerie : ce qu'il y a sur les comptes bancaires."
        />
        <Ligne
          label="Taxe à reverser"
          cents={dossier.tva_a_payer_cts}
          aide="La TVA à payer à l'administration."
        />
      </dl>
    </section>
  );
}

export function ClotureSection({
  dossier,
  comptesClos,
  operationsRestantes,
}: {
  dossier: DossierResume;
  comptesClos: boolean;
  operationsRestantes: number;
}) {
  const [erreur, setErreur] = useState<string | null>(null);
  const [avertissementLiasse, setAvertissementLiasse] = useState(false);
  const [liasseLue, setLiasseLue] = useState(false);
  const bloque = operationsRestantes > 0 || !comptesClos;

  function ouvrirAvertissement() {
    if (bloque) return;
    setLiasseLue(false);
    setAvertissementLiasse(true);
  }

  function fermerAvertissement() {
    setAvertissementLiasse(false);
  }

  async function telecharger(document: DocumentCloture) {
    setErreur(null);
    // Même schéma de nom que le Content-Disposition côté serveur
    // (demo_api.py : "liasse-{dossier_id}.pdf" etc.) — utile dès qu'on
    // télécharge plusieurs dossiers dans le même dossier de téléchargements.
    const [nom, extension] = document.split(/\.(?=[^.]+$)/);
    const nomFichier = `${nom}-${dossier.dossier_id}.${extension}`;
    try {
      await telechargerAvecAuthChauffeur(
        cheminTelechargementCloture(dossier.dossier_id, document),
        nomFichier,
      );
    } catch (exception) {
      setErreur(
        phrasePourChauffeur(
          exception instanceof ErreurAuthChauffeur
            ? exception.message
            : "Échec du téléchargement.",
        ),
      );
    }
  }

  return (
    <section className="mt-8">
      <h2 className="text-base font-semibold text-ink">Pour les impôts</h2>
      <p className="mt-1 text-sm text-ink">{texteDocuments(operationsRestantes, comptesClos)}</p>
      <div className={bloque ? "opacity-50" : undefined}>
      <Button
        type="button"
        variant="secondary"
        className="mt-4 w-full"
        disabled={bloque}
        onClick={ouvrirAvertissement}
      >
        Récupérer la liasse
      </Button>
      {avertissementLiasse && (
        <Dialogue titre="Liasse de l'exercice" titreId="titre-liasse" onFermer={fermerAvertissement}>
          <p className="mt-4 text-sm text-subtle">
            La signature électronique arrivera plus tard. En attendant, cette validation engage
            sur la liasse telle qu&apos;elle est.
          </p>
          <label className="mt-4 flex min-h-11 items-start gap-3 text-sm text-ink">
            <input
              type="checkbox"
              className="mt-0.5 size-6 shrink-0"
              checked={liasseLue}
              onChange={(event) => setLiasseLue(event.target.checked)}
            />
            <span>Je reconnais avoir lu et validé le dossier fiscal (la liasse).</span>
          </label>
          <div className="mt-5 flex gap-2">
            <Button type="button" variant="ghost" className="h-11 flex-1" onClick={fermerAvertissement}>
              Annuler
            </Button>
            <Button
              type="button"
              className="h-11 flex-1"
              disabled={!liasseLue}
              onClick={() => {
                fermerAvertissement();
                void telecharger(LIASSE);
              }}
            >
              Télécharger
            </Button>
          </div>
        </Dialogue>
      )}
      <p className="mt-4 text-sm text-subtle">
        Le FEC est le fichier que l&apos;administration demande lors d&apos;un
        contrôle. Il liste chaque écriture, au format texte, pas en PDF.
      </p>
      <ul className="mt-2">
        {[pieceDeclaration(dossier), ...PIECES].map(({ document, label, detail, aide }) => (
          <li key={document} className="flex items-center gap-2 border-b border-hairline">
            <span className="flex min-w-0 flex-1 items-center py-3 pl-2 text-sm font-medium text-ink">
              {label}
              <Aide texte={aide} />
            </span>
            <button
              type="button"
              aria-label={`Télécharger ${label} (${detail})`}
              disabled={bloque}
              onClick={() => void telecharger(document)}
              className="flex min-h-11 shrink-0 cursor-pointer items-center gap-2 rounded-md px-2 py-3 text-sm text-subtle outline-none hover:bg-primary-subtle focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#2563eb] disabled:cursor-not-allowed"
            >
              {detail}
              <Download className="h-4 w-4 text-primary" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      </div>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}

function Ligne({
  label,
  cents,
  aide,
}: {
  label: string;
  cents: number;
  aide?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-subtle">
        {label}
        {aide && <Aide texte={aide} />}
      </dt>
      <dd className={`tabular-nums text-right ${cents < 0 ? "text-amount-negative" : "text-ink"}`}>
        {formatMontant(cents)}
      </dd>
    </div>
  );
}
