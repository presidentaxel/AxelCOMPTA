"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/Badge";
import { DocumentsImport, ExercicesImport } from "@/components/DocumentsImport";
import { FormulaireSectionImport } from "@/components/SectionImport";
import { SqueletteLignes } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  ErreurAuthGestionnaire,
  changerStatutImport,
  completerFicheImport,
  creerChauffeurImport,
  lireFicheImport,
  relireRegistresImport,
} from "@/lib/auth-gestionnaire";
import {
  STATUTS_IMPORT,
  badgeStatut,
  etatSection,
  libelleStatut,
  nomChauffeur,
  type FicheImport,
  type SectionImport,
} from "@/lib/fiches-import";
import { messageEchecChargement } from "@/lib/session";
import { useDroitGestionnaire } from "@/lib/use-droit";

const DOCUMENTS_REPRISE = ["liasse", "fec", "balance", "grand_livre", "autre"];
const DOCUMENTS_ADMINISTRATIFS = ["kbis", "statuts", "rib", "lettre_comptable", "autre"];
const DOCUMENTS_BANQUE = ["releve_bancaire", "rib", "autre"];

export default function FicheImportPage() {
  return (
    <Suspense fallback={<SqueletteLignes nombre={6} className="h-24" />}>
      <FicheImportEcran />
    </Suspense>
  );
}

/** AXE-941 : une fiche d'import. L'écran d'ensemble montre une carte par
 * catégorie et ce qui lui manque ; un clic ouvre ses champs (`?section=`). */
function FicheImportEcran() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const recherche = useSearchParams();
  const droit = useDroitGestionnaire();
  const [fiche, setFiche] = useState<FicheImport | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const cleSection = recherche.get("section");

  const charger = useCallback(() => {
    lireFicheImport(id)
      .then(setFiche)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur(messageEchecChargement(exception, "La fiche n'a pas pu être chargée."));
      });
  }, [id, router]);
  useEffect(charger, [charger]);

  if (erreur) return <p role="alert" className="text-sm text-danger">{erreur}</p>;
  if (fiche === null) return <SqueletteLignes nombre={6} className="h-24" />;

  const modifiable = droit.ecriture && fiche.statut !== "traitee";
  const section = fiche.sections_detail.find((s) => s.cle === cleSection) ?? null;
  const ouvrir = (cle: string | null) => router.push(cle ? `/imports/${id}?section=${cle}` : `/imports/${id}`);

  return (
    <div className="space-y-6">
      <Link href="/imports" className="text-sm text-subtle hover:text-ink">
        ← Imports
      </Link>
      <EnTeteFiche fiche={fiche} ecriture={droit.ecriture} onFiche={setFiche} />
      {section === null ? (
        <>
          <ChauffeurDuPortefeuille fiche={fiche} ecriture={droit.ecriture} onFiche={setFiche} />
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {fiche.sections_detail.map((s) => (
              <CarteSection key={s.cle} section={s} onOuvrir={() => ouvrir(s.cle)} />
            ))}
          </ul>
        </>
      ) : (
        <VueSection
          fiche={fiche}
          section={section}
          modifiable={modifiable}
          onFiche={setFiche}
          onRetour={() => ouvrir(null)}
        />
      )}
    </div>
  );
}

function EnTeteFiche({
  fiche,
  ecriture,
  onFiche,
}: {
  fiche: FicheImport;
  ecriture: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  const [message, setMessage] = useState<string | null>(null);

  async function agir(action: () => Promise<FicheImport>) {
    setMessage(null);
    try {
      onFiche(await action());
    } catch (exception) {
      setMessage(exception instanceof Error ? exception.message : "Erreur inattendue.");
    }
  }

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-ink">{nomChauffeur(fiche)}</h1>
        <Badge variant={badgeStatut(fiche.statut)}>{libelleStatut(fiche.statut)}</Badge>
      </div>
      <p className="text-sm text-subtle">
        {fiche.denomination ?? "Entreprise à compléter"}
        {fiche.siren && ` · SIREN ${fiche.siren}`} · {fiche.sections_completes}/{fiche.sections} catégories
        complètes
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {ecriture &&
          STATUTS_IMPORT.map((s) => (
            <Button
              key={s.cle}
              size="sm"
              variant={fiche.statut === s.cle ? "secondary" : "ghost"}
              aria-pressed={fiche.statut === s.cle}
              onClick={() => fiche.statut !== s.cle && agir(() => changerStatutImport(fiche.id, s.cle))}
            >
              {s.libelle}
            </Button>
          ))}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => navigator.clipboard.writeText(window.location.href).then(() => setMessage("Lien copié."))}
        >
          Copier le lien de la fiche
        </Button>
      </div>
      <p className="text-sm text-subtle">
        {fiche.registre_lu_le
          ? `Préremplie par l'INSEE et le RNE le ${new Date(fiche.registre_lu_le).toLocaleDateString("fr-FR")}.`
          : "Pas encore lue aux registres : indiquez le SIREN dans Entreprise."}{" "}
        {ecriture && fiche.siren && fiche.statut !== "traitee" && (
          <button
            type="button"
            className="font-medium text-ink underline underline-offset-4"
            onClick={() => agir(() => relireRegistresImport(fiche.id))}
          >
            Relire les registres
          </button>
        )}
      </p>
      {message && <p role="status" className="text-sm text-subtle">{message}</p>}
    </header>
  );
}

function ChauffeurDuPortefeuille({
  fiche,
  ecriture,
  onFiche,
}: {
  fiche: FicheImport;
  ecriture: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  if (fiche.dossier_id) {
    return (
      <Card variant="flat">
        <p className="text-sm text-ink">
          {fiche.dossier_cree
            ? `Chauffeur ajouté au portefeuille (${fiche.dossier_id}). Il sera invité dans son app plus tard.`
            : `Ajout au portefeuille en cours (${fiche.dossier_id}) : le dossier apparaît dans Entreprises d'ici une minute.`}
        </p>
      </Card>
    );
  }
  return (
    <Card variant="flat" className="space-y-2">
      <p className="text-sm text-ink">
        {fiche.manque_pour_creer.length === 0
          ? "La fiche suffit pour ajouter le chauffeur au portefeuille. Le reste peut se compléter ensuite."
          : `Pour ajouter le chauffeur au portefeuille, il manque : ${fiche.manque_pour_creer.join(", ")}.`}
      </p>
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
      {ecriture && (
        <Button
          size="sm"
          disabled={envoi || fiche.manque_pour_creer.length > 0}
          onClick={async () => {
            setEnvoi(true);
            setErreur(null);
            try {
              onFiche(await creerChauffeurImport(fiche.id));
            } catch (exception) {
              setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
            } finally {
              setEnvoi(false);
            }
          }}
        >
          Ajouter le chauffeur au portefeuille
        </Button>
      )}
    </Card>
  );
}

function CarteSection({ section, onOuvrir }: { section: SectionImport; onOuvrir: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onOuvrir}
        className="h-full w-full rounded-lg border border-border bg-canvas p-5 text-left transition-colors hover:bg-surface-soft"
      >
        <span className="flex items-center justify-between gap-2">
          <span className="font-medium text-ink">{section.libelle}</span>
          <Badge variant={section.complet ? "validated" : "pending"}>{etatSection(section)}</Badge>
        </span>
        <span className="mt-1 block text-sm text-subtle">{section.description}</span>
        {section.manquants.length > 0 && (
          <span className="mt-2 block text-xs text-muted">
            Manque : {section.manquants.slice(0, 3).join(", ")}
            {section.manquants.length > 3 && "…"}
          </span>
        )}
      </button>
    </li>
  );
}

function VueSection({
  fiche,
  section,
  modifiable,
  onFiche,
  onRetour,
}: {
  fiche: FicheImport;
  section: SectionImport;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
  onRetour: () => void;
}) {
  const documents =
    section.cle === "reprise"
      ? DOCUMENTS_REPRISE
      : section.cle === "documents"
        ? DOCUMENTS_ADMINISTRATIFS
        : section.cle === "banque"
          ? DOCUMENTS_BANQUE
          : null;
  return (
    <section className="space-y-6" aria-labelledby="titre-section">
      <div>
        <Button size="sm" variant="ghost" onClick={onRetour}>
          ← Toutes les catégories
        </Button>
        <h2 id="titre-section" className="mt-2 text-xl font-semibold text-ink">
          {section.libelle}
        </h2>
        <p className="mt-1 text-sm text-subtle">{section.description}</p>
        {section.manquants.length > 0 && (
          <p className="mt-2 text-sm text-ink">Manque : {section.manquants.join(", ")}.</p>
        )}
        {!modifiable && fiche.statut === "traitee" && (
          <p className="mt-2 text-sm text-subtle">Fiche traitée : repassez-la en traitement pour la modifier.</p>
        )}
      </div>
      <FormulaireSectionImport
        key={section.cle}
        section={section}
        modifiable={modifiable}
        onEnregistrer={async (champs) => onFiche(await completerFicheImport(fiche.id, champs))}
      />
      {section.cle === "reprise" && <ExercicesImport fiche={fiche} />}
      {documents && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-ink">Documents</h3>
          <DocumentsImport fiche={fiche} modifiable={modifiable} categories={documents} onFiche={onFiche} />
        </div>
      )}
    </section>
  );
}
