"use client";

import { Fragment, useEffect, useId, useState } from "react";

import { Montant } from "@/components/Montant";
import { PanneauEtat } from "@/components/PanneauEtat";
import { SqueletteLignes } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, type SelectOption } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { motifValide } from "@/lib/anomalies";
import { imputerExpert, lireClassees, noterVerdict } from "@/lib/auth-gestionnaire";
import {
  changer,
  type Cle,
  type EtatClassees,
  formatConfiance,
  ORIGINES,
  phraseCompteurs,
  SENS,
  STATUTS,
  TRANCHES,
  TRIS,
  versApi,
} from "@/lib/classees";
import { filtresActifs, sansFiltres, versFileATraiter } from "@/lib/classees-filtres";
import { formatDate } from "@/lib/format";
import { phraseTva } from "@/lib/tva-estimee";
import { messageEchecChargement } from "@/lib/session";
import type { OperationClassee, OperationsClassees as Donnees } from "@/lib/types";

/** Radix interdit une option de valeur vide (voir `ui/select`) : « Toutes »
 * porte cette valeur, que l'état de la vue lit comme « pas de filtre ». */
const TOUS = "__tous__";

/** Ce qui est déjà classé, et par qui ou quoi (AXE-823). « Juste » note sans
 * écrire ; « Ce classement est faux » note, puis propose l'imputation. */
export function OperationsClassees({
  etat,
  comptes,
  ecriture,
  onChanger,
}: {
  etat: EtatClassees;
  comptes: { compte: string; libelle: string }[];
  ecriture: boolean;
  onChanger: (suivant: EtatClassees) => void;
}) {
  const [donnees, setDonnees] = useState<Donnees | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const requete = versApi(etat).toString();

  useEffect(() => {
    let actif = true;
    lireClassees(new URLSearchParams(requete))
      .then((reponse) => {
        if (!actif) return;
        setDonnees(reponse);
        setErreur(null);
      })
      .catch((exception: unknown) => {
        if (actif) {
          setErreur(messageEchecChargement(exception, "Les opérations classées n'ont pas pu être lues."));
        }
      });
    return () => {
      actif = false;
    };
  }, [requete, version]);

  function choisir(cle: Cle, valeur: string) {
    onChanger(changer(etat, cle, valeur));
  }

  return (
    <div className="mt-6">
      {donnees && <p className="text-sm text-ink">{phraseCompteurs(donnees.compteurs)}.</p>}
      <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Choix libelle="Origine" valeur={etat.origine} options={ORIGINES} onChoisir={(v) => choisir("origine", v)} />
        <Choix
          libelle="Catégorie"
          valeur={etat.categorie}
          options={Object.fromEntries((donnees?.categories ?? []).map((c) => [c, c]))}
          onChoisir={(v) => choisir("categorie", v)}
        />
        <Choix libelle="Confiance" valeur={etat.tranche} options={TRANCHES} onChoisir={(v) => choisir("tranche", v)} />
        <Choix libelle="Sens" valeur={etat.sens} options={SENS} onChoisir={(v) => choisir("sens", v)} />
        <Choix libelle="Tri" valeur={etat.tri} options={TRIS} onChoisir={(v) => choisir("tri", v)} sansTous />
      </div>
      {erreur && (
        <div className="mt-6">
          <PanneauEtat
            type="erreur"
            message={erreur}
            action={{
              libelle: "Réessayer",
              onClick: () => {
                setErreur(null);
                setVersion((v) => v + 1);
              },
            }}
          />
        </div>
      )}
      {!donnees && !erreur && (
        <div className="mt-6">
          <SqueletteLignes nombre={5} className="h-10 w-full" />
        </div>
      )}
      {donnees && donnees.operations.length === 0 && (
        <div className="mt-6">
          <PanneauEtat
            type="vide"
            message={
              filtresActifs(etat)
                ? "Aucune opération pour ces filtres."
                : "Aucune opération classée dans cette vue."
            }
            action={
              filtresActifs(etat)
                ? { libelle: "Réinitialiser les filtres", onClick: () => onChanger(sansFiltres(etat)) }
                : { libelle: "Voir la file à traiter", onClick: () => onChanger(versFileATraiter(etat)) }
            }
          />
        </div>
      )}
      {donnees && donnees.operations.length > 0 && (
        <Card variant="section" className="mt-4 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-32">Date</TableHead>
                <TableHead>Opération</TableHead>
                <TableHead>Classement</TableHead>
                <TableHead montant>Montant</TableHead>
                {ecriture && <TableHead>Verdict</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {donnees.operations.map((operation) => (
                <Ligne
                  key={`${operation.dossier_id}-${operation.ecriture_id}`}
                  operation={operation}
                  comptes={comptes}
                  ecriture={ecriture}
                  onFait={() => setVersion((v) => v + 1)}
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
      {donnees && donnees.pages > 1 && (
        <div className="mt-4 flex items-center gap-3 text-sm text-subtle">
          <Button
            type="button"
            variant="secondary"
            disabled={donnees.page <= 1}
            onClick={() => choisir("page", String(donnees.page - 1))}
          >
            Page précédente
          </Button>
          <span>
            Page {donnees.page} sur {donnees.pages} · {donnees.total} opérations
          </span>
          <Button
            type="button"
            variant="secondary"
            disabled={donnees.page >= donnees.pages}
            onClick={() => choisir("page", String(donnees.page + 1))}
          >
            Page suivante
          </Button>
        </div>
      )}
    </div>
  );
}

function phraseTvaOperation(operation: OperationClassee) {
  const phrase = phraseTva(
    operation.tva_estimee_cts,
    operation.tva_relevee_cts,
    operation.montant_cts,
    false,
  );
  return phrase ? <span className="mt-1 block text-sm text-ink">{phrase}</span> : null;
}

function Choix({
  libelle,
  valeur,
  options,
  onChoisir,
  sansTous = false,
}: {
  libelle: string;
  valeur: string;
  options: Record<string, string>;
  onChoisir: (valeur: string) => void;
  sansTous?: boolean;
}) {
  const id = useId();
  const liste: SelectOption[] = Object.entries(options).map(([value, label]) => ({ value, label }));
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm font-medium text-subtle">
        {libelle}
      </label>
      <Select
        id={id}
        className="w-52"
        value={valeur === "" ? TOUS : valeur}
        onValueChange={(choisie) => onChoisir(choisie === TOUS ? "" : choisie)}
        options={sansTous ? liste : [{ value: TOUS, label: "Toutes" }, ...liste]}
      />
    </div>
  );
}

function Ligne({
  operation,
  comptes,
  ecriture,
  onFait,
}: {
  operation: OperationClassee;
  comptes: { compte: string; libelle: string }[];
  ecriture: boolean;
  onFait: () => void;
}) {
  const [corriger, setCorriger] = useState(false);
  const [compte, setCompte] = useState("");
  const [motif, setMotif] = useState(""); // AXE-800 : obligatoire
  const [erreur, setErreur] = useState<string | null>(null);

  const messageEchec = (exception: unknown) =>
    setErreur(
      exception instanceof Error ? exception.message : "Cette opération n'a pas pu être modifiée. Réessayez.",
    );

  function verdict(valeur: "juste" | "faux") {
    setErreur(null);
    noterVerdict(operation.dossier_id, operation.ecriture_id, valeur)
      .then(() => {
        if (valeur === "faux") setCorriger(true);
        onFait();
      })
      .catch(messageEchec);
  }

  function imputer() {
    setErreur(null);
    imputerExpert(operation.dossier_id, operation.ecriture_id, compte, motif.trim())
      .then(() => {
        setCorriger(false);
        onFait();
      })
      .catch(messageEchec);
  }

  return (
    <Fragment>
      <TableRow>
        <TableCell className="py-2 whitespace-nowrap tabular-nums text-subtle">
          {formatDate(operation.date)}
        </TableCell>
        <TableCell className="py-2">
          <span className="block font-medium text-ink">{operation.libelle}</span>
          <span className="block text-xs text-subtle">
            {operation.dossier_nom} · {STATUTS[operation.statut] ?? operation.statut}
          </span>
        </TableCell>
        <TableCell className="py-2 text-xs text-subtle">
          Compte {operation.compte}
          {operation.categorie ? ` · ${operation.categorie}` : ""} · {ORIGINES[operation.origine] ?? operation.origine} ·
          confiance {formatConfiance(operation.confiance)}
          {operation.verdict ? ` · noté ${operation.verdict}` : ""}
          {phraseTvaOperation(operation)}
          {erreur && (
            <span role="alert" className="mt-1 block text-sm text-danger">
              {erreur}
            </span>
          )}
        </TableCell>
        <TableCell montant className="py-2">
          <Montant centimes={operation.montant_cts} />
        </TableCell>
        {ecriture && (
          <TableCell className="py-2">
            <span className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => verdict("juste")}>
                Juste
              </Button>
              <Button type="button" variant="ghost" onClick={() => verdict("faux")}>
                Ce classement est faux
              </Button>
            </span>
          </TableCell>
        )}
      </TableRow>
      {ecriture && corriger && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={5} className="bg-canvas-app py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Select
                aria-label="Compte correct"
                className="w-80"
                placeholder="Compte correct…"
                value={compte}
                onValueChange={setCompte}
                options={comptes.map((choix) => ({
                  value: choix.compte,
                  label: `${choix.compte} · ${choix.libelle}`,
                }))}
              />
              <Input
                aria-label="Motif de la correction"
                placeholder="Motif (obligatoire)"
                value={motif}
                onChange={(evenement) => setMotif(evenement.target.value)}
                className="w-80"
              />
              <Button type="button" disabled={!compte || motifValide(motif) === null} onClick={imputer}>
                Imputer
              </Button>
            </div>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  );
}
