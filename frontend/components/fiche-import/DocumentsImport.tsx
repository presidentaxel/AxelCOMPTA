"use client";

import { AlertTriangle, Check, Download, FileText, LoaderCircle, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/ui/button";
import {
  deposerDocumentImport,
  retirerDocumentImport,
  telechargerDocumentImport,
} from "@/lib/auth-gestionnaire";
import {
  basculerRetard,
  libelleTraitement,
  parExercice,
  phraseExercice,
  retardPossible,
  taille,
  valeurChamp,
  type DocumentImport,
  type EmplacementImport,
  type ExerciceImport,
  type FicheImport,
} from "@/lib/fiches-import";

const FORMATS = ".pdf,.qif,.csv,.txt,.xml,.xls,.xlsx,.ods,.jpg,.jpeg,.png,.zip";
type Envoi = { cle: string; nom: string; erreur?: string };

/** AXE-947 : les emplacements d'une catégorie, un par document attendu.
 * En reprise, rangés par exercice. */
export function EmplacementsSection({
  fiche,
  section,
  modifiable,
  onFiche,
  enregistrer,
}: {
  fiche: FicheImport;
  section: string;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
  enregistrer: (champs: Record<string, string>) => Promise<void>;
}) {
  const siens = fiche.emplacements.filter((e) => e.section === section);
  if (siens.length === 0) return null;
  const groupes = new Map(parExercice(siens));
  const liste = (emplacements: EmplacementImport[]) => (
    <ul className="divide-y divide-hairline border-y border-border">
      {emplacements.map((e) => (
        <CarteEmplacement key={e.cle} fiche={fiche} emplacement={e} modifiable={modifiable} onFiche={onFiche} />
      ))}
    </ul>
  );
  if (section !== "reprise") return liste(siens);
  const exercices = [...fiche.exercices].sort((a, b) => b.annee - a.annee);
  return (
    <div className="space-y-6">
      {exercices.map((e) => (
        <div key={e.annee} className="space-y-3">
          <EnTeteExercice
            exercice={e}
            enRetard={valeurChamp(fiche, "en_retard")}
            modifiable={modifiable}
            enregistrer={enregistrer}
          />
          {liste(groupes.get(e.annee) ?? [])}
        </div>
      ))}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-ink">Autres documents</h3>
        {liste(groupes.get(null) ?? [])}
      </div>
    </div>
  );
}

/** AXE-950 : l'exercice, son rôle pour la reprise et, une fois la date
 * limite passée, « Pas déposée (en retard) ». */
function EnTeteExercice({
  exercice,
  enRetard,
  modifiable,
  enregistrer,
}: {
  exercice: ExerciceImport;
  enRetard: string;
  modifiable: boolean;
  enregistrer: (champs: Record<string, string>) => Promise<void>;
}) {
  const [envoi, setEnvoi] = useState(false);
  const du = new Date(exercice.debut).toLocaleDateString("fr-FR");
  const au = new Date(exercice.fin).toLocaleDateString("fr-FR");
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">
          Exercice {exercice.annee}{" "}
          <span className="font-normal text-subtle">
            du {du} au {au}
          </span>
        </h3>
        <p className="mt-0.5 text-xs text-subtle">{phraseExercice(exercice)}</p>
      </div>
      {modifiable && retardPossible(exercice) && (
        <Button
          size="sm"
          variant={exercice.en_retard ? "secondary" : "ghost"}
          aria-pressed={exercice.en_retard}
          disabled={envoi}
          onClick={async () => {
            setEnvoi(true);
            try {
              await enregistrer({ en_retard: basculerRetard(enRetard, exercice.annee) });
            } finally {
              setEnvoi(false);
            }
          }}
        >
          {envoi && <LoaderCircle className="size-3.5 animate-spin" aria-hidden />}
          {exercice.en_retard ? "Pas déposée (en retard)" : "Liasse pas déposée ?"}
        </Button>
      )}
    </div>
  );
}

function CarteEmplacement({
  fiche,
  emplacement,
  modifiable,
  onFiche,
}: {
  fiche: FicheImport;
  emplacement: EmplacementImport;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  const [survol, setSurvol] = useState(false);
  const [envois, setEnvois] = useState<Envoi[]>([]);
  const entree = useRef<HTMLInputElement>(null);
  const rempli = emplacement.documents.length > 0;

  async function deposer(fichiers: FileList | null) {
    const liste = Array.from(fichiers ?? []);
    const nouveaux = liste.map((f, i) => ({ cle: `${Date.now()}-${i}`, nom: f.name }));
    setEnvois((avant) => [...avant, ...nouveaux]); // visibles tout de suite
    for (const [i, fichier] of liste.entries()) {
      try {
        onFiche(await deposerDocumentImport(fiche.id, fichier, emplacement.cle));
        setEnvois((avant) => avant.filter((e) => e.cle !== nouveaux[i].cle));
      } catch (exception) {
        const erreur = exception instanceof Error ? exception.message : "Erreur inattendue.";
        setEnvois((avant) => avant.map((e) => (e.cle === nouveaux[i].cle ? { ...e, erreur } : e)));
      }
    }
  }

  return (
    <li
      onDragOver={(e) => {
        if (!modifiable) return;
        e.preventDefault();
        setSurvol(true);
      }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(e) => {
        e.preventDefault();
        setSurvol(false);
        if (modifiable) void deposer(e.dataTransfer.files);
      }}
      className={`flex flex-col gap-3 py-4 transition-colors ${survol ? "bg-surface-soft" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-ink">{emplacement.libelle}</p>
          <p className="mt-0.5 text-xs text-subtle">{emplacement.explication}</p>
        </div>
        <Badge variant={rempli ? "validated" : emplacement.attendu ? "pending" : "missing"}>
          {rempli ? "Reçu" : emplacement.attendu ? "Attendu" : "Facultatif"}
        </Badge>
      </div>
      {(emplacement.documents.length > 0 || envois.length > 0) && (
        <ul className="space-y-2">
          {emplacement.documents.map((d) => (
            <LigneDocument key={d.id} fiche={fiche} document={d} modifiable={modifiable} onFiche={onFiche} />
          ))}
          {envois.map((e) => (
            <li key={e.cle} className="flex items-center gap-2 text-sm">
              {e.erreur ? (
                <AlertTriangle className="size-4 text-danger" aria-hidden />
              ) : (
                <LoaderCircle className="size-4 animate-spin text-muted" aria-hidden />
              )}
              <span className="truncate text-ink">{e.nom}</span>
              {e.erreur && <span className="text-xs text-danger">{e.erreur}</span>}
            </li>
          ))}
        </ul>
      )}
      {modifiable && (
        <>
          <button
            type="button"
            onClick={() => entree.current?.click()}
            className="inline-flex items-center gap-2 text-sm text-subtle transition-colors hover:text-ink"
          >
            <UploadCloud className="size-4" aria-hidden />
            Déposer ou glisser un fichier
          </button>
          <input
            ref={entree}
            type="file"
            multiple
            className="sr-only"
            aria-label={`Déposer : ${emplacement.libelle}`}
            accept={FORMATS}
            onChange={(e) => {
              void deposer(e.target.files);
              e.target.value = "";
            }}
          />
        </>
      )}
    </li>
  );
}

function LigneDocument({
  fiche,
  document,
  modifiable,
  onFiche,
}: {
  fiche: FicheImport;
  document: DocumentImport;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  async function ouvrir() {
    const blob = await telechargerDocumentImport(fiche.id, document.id);
    const lien = window.document.createElement("a");
    lien.href = URL.createObjectURL(blob);
    lien.download = document.nom_fichier;
    lien.click();
    URL.revokeObjectURL(lien.href);
  }

  const couleur =
    document.statut_traitement === "traite"
      ? "text-success"
      : document.statut_traitement === "illisible"
        ? "text-danger"
        : "text-warning";
  return (
    <li className="py-1.5">
      <div className="flex items-center gap-2 text-sm">
        <FileText className="size-4 shrink-0 text-subtle" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-ink" title={document.nom_fichier}>
          {document.nom_fichier}
          <span className="ml-2 text-xs text-muted">{taille(document.taille)}</span>
        </span>
        <Button size="sm" variant="ghost" onClick={ouvrir} aria-label={`Télécharger ${document.nom_fichier}`}>
          <Download className="size-4" aria-hidden />
        </Button>
        {modifiable && (
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Retirer ${document.nom_fichier}`}
            onClick={async () => {
              if (window.confirm(`Retirer ${document.nom_fichier} ?`)) {
                onFiche(await retirerDocumentImport(fiche.id, document.id));
              }
            }}
          >
            <Trash2 className="size-4" aria-hidden />
          </Button>
        )}
      </div>
      <p className={`mt-1 flex items-center gap-1 text-xs ${couleur}`}>
        {document.statut_traitement === "traite" && <Check className="size-3.5" aria-hidden />}
        <span className="font-medium">{libelleTraitement(document.statut_traitement)}</span>
        {document.resume && <span className="text-subtle">· {document.resume}</span>}
      </p>
    </li>
  );
}
