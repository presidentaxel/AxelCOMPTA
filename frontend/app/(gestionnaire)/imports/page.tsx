"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/Badge";
import { SqueletteLignes } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErreurAuthGestionnaire, deciderFicheImport, listerFichesImport, ouvrirFicheImport } from "@/lib/auth-gestionnaire";
import {
  STATUTS_IMPORT,
  badgeStatut,
  fichesActives,
  libelleStatut,
  nomChauffeur,
  progression,
  type FicheImportResume,
  type StatutImport,
} from "@/lib/fiches-import";
import { messageEchecChargement } from "@/lib/session";
import { useDroitGestionnaire } from "@/lib/use-droit";

type Filtre = "toutes" | StatutImport;

/** AXE-941 : les chauffeurs à reprendre. On ouvre une fiche avec le nom et
 * le prénom (et le SIREN si on l'a), puis on la complète catégorie par
 * catégorie. Plusieurs personnes peuvent travailler sur la même fiche. */
export default function ImportsPage() {
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const [fiches, setFiches] = useState<FicheImportResume[] | null>(null);
  const [filtre, setFiltre] = useState<Filtre>("toutes");
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    listerFichesImport()
      .then(setFiches)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur(messageEchecChargement(exception, "Les imports n'ont pas pu être chargés."));
      });
  }, [router]);

  const toutes = fichesActives(fiches ?? []);
  const visibles = filtre === "toutes" ? toutes : (fiches ?? []).filter((f) => f.statut === filtre);
  const nombre = (statut: StatutImport) => (fiches ?? []).filter((f) => f.statut === statut).length;

  async function decider(id: string, decision: "ignorer" | "reprendre") {
    setErreur(null);
    try {
      const suivante = await deciderFicheImport(id, decision);
      setFiches((actuelles) =>
        (actuelles ?? []).map((fiche) =>
          fiche.id === id ? { ...fiche, statut: suivante.statut, maj_le: suivante.maj_le, maj_par: suivante.maj_par } : fiche,
        ),
      );
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Imports</h1>
        <p className="mt-1 max-w-2xl text-sm text-subtle">
          Une fiche par chauffeur à reprendre : entreprise, dirigeant, fiscalité, reprise comptable, banque,
          plateformes et documents. Le SIREN préremplit l&apos;entreprise depuis l&apos;INSEE et le RNE.
        </p>
      </header>

      {droit.ecriture && <NouvelImport onOuverte={(id) => router.push(`/imports/${id}`)} />}

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrer par statut">
        <BoutonFiltre actif={filtre === "toutes"} onClick={() => setFiltre("toutes")}>
          Toutes ({fiches === null ? 0 : toutes.length})
        </BoutonFiltre>
        {STATUTS_IMPORT.map((s) => (
          <BoutonFiltre key={s.cle} actif={filtre === s.cle} onClick={() => setFiltre(s.cle)}>
            {s.libelle} ({nombre(s.cle)})
          </BoutonFiltre>
        ))}
      </div>

      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
      {fiches === null && !erreur && <SqueletteLignes nombre={4} className="h-10" />}
      {fiches !== null && visibles.length === 0 && (
        <p className="text-sm text-subtle">Aucune fiche {filtre === "toutes" ? "pour l'instant" : "avec ce statut"}.</p>
      )}
      {visibles.length > 0 && (
        <TableFiches fiches={visibles} ecriture={droit.ecriture} onDecider={(id, decision) => void decider(id, decision)} />
      )}
    </div>
  );
}

function BoutonFiltre({ actif, onClick, children }: { actif: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <Button variant={actif ? "secondary" : "ghost"} size="sm" aria-pressed={actif} onClick={onClick}>
      {children}
    </Button>
  );
}

function NouvelImport({ onOuverte }: { onOuverte: (id: string) => void }) {
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [siren, setSiren] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function ouvrir(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnvoi(true);
    setErreur(null);
    try {
      onOuverte((await ouvrirFicheImport(nom, prenom, siren)).id);
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
      setEnvoi(false);
    }
  }

  return (
    <form onSubmit={ouvrir} aria-labelledby="titre-nouvel-import" className="space-y-3 border-y border-border py-4">
        <p id="titre-nouvel-import" className="text-sm font-medium text-ink">
          Nouvel import
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm text-ink">
            Prénom
            <Input className="mt-1" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
          </label>
          <label className="text-sm text-ink">
            Nom
            <Input className="mt-1" value={nom} onChange={(e) => setNom(e.target.value)} />
          </label>
          <label className="text-sm text-ink">
            SIREN ou SIRET (facultatif)
            <Input
              className="mt-1"
              inputMode="numeric"
              value={siren}
              onChange={(e) => setSiren(e.target.value)}
              placeholder="9 ou 14 chiffres"
            />
          </label>
        </div>
        {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
        <Button type="submit" disabled={envoi || (!nom.trim() && !prenom.trim())}>
          {envoi ? "Ouverture…" : "Ouvrir la fiche"}
        </Button>
    </form>
  );
}

function TableFiches({
  fiches,
  ecriture,
  onDecider,
}: {
  fiches: FicheImportResume[];
  ecriture: boolean;
  onDecider: (id: string, decision: "ignorer" | "reprendre") => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Chauffeur</TableHead>
          <TableHead>Entreprise</TableHead>
          <TableHead>Statut</TableHead>
          <TableHead>Avancement</TableHead>
          <TableHead>Dernière modification</TableHead>
          {ecriture && <TableHead className="text-right"> </TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {fiches.map((fiche) => (
          <TableRow key={fiche.id}>
            <TableCell>
              <Link href={`/imports/${fiche.id}`} className="font-medium text-ink underline-offset-4 hover:underline">
                {nomChauffeur(fiche)}
              </Link>
            </TableCell>
            <TableCell className="text-subtle">
              {fiche.denomination ?? "—"}
              {fiche.siren && <span className="ml-2 text-xs text-muted">{fiche.siren}</span>}
            </TableCell>
            <TableCell>
              <Badge variant={badgeStatut(fiche.statut)}>{libelleStatut(fiche.statut)}</Badge>
            </TableCell>
            <TableCell className="text-subtle">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-soft" aria-hidden>
                  <div className="h-full rounded-full bg-ink" style={{ width: `${progression(fiche)}%` }} />
                </div>
                <span className="text-xs">
                  {fiche.sections_completes}/{fiche.sections}
                </span>
              </div>
              {fiche.dossier_id && <span className="text-xs text-muted">Chauffeur ajouté</span>}
            </TableCell>
            <TableCell className="text-subtle">
              {new Date(fiche.maj_le).toLocaleDateString("fr-FR")} · {fiche.maj_par}
            </TableCell>
            {ecriture && (
              <TableCell className="text-right">
                {fiche.statut === "ignore" ? (
                  <Button type="button" variant="secondary" size="sm" onClick={() => onDecider(fiche.id, "reprendre")}>
                    Remettre
                  </Button>
                ) : (
                  <Button type="button" variant="ghost" size="sm" onClick={() => onDecider(fiche.id, "ignorer")}>
                    Ignorer
                  </Button>
                )}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
