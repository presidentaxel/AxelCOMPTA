"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SelectRecherche } from "@/components/ui/select-recherche";
import {
  ErreurAuthGestionnaire,
  lireManquesRapprochementExpert,
  lireRapprochementsExpert,
  ModeExpertRefuse,
  trancherSemaineExpert,
} from "@/lib/auth-gestionnaire";
import { changer, type EtatClassees } from "@/lib/classees";
import { formatDate, formatMontant } from "@/lib/format";
import { messageEchecChargement } from "@/lib/session";
import type { SemaineRapprochement } from "@/lib/types";

const ETATS: Record<string, string> = {
  solde: "Soldée",
  en_attente: "En attente",
  a_verifier: "À vérifier",
};

const NATURES: Record<string, string> = {
  hebdomadaire: "Virement de la semaine",
  instantane: "Virement instantané",
};

/** Chaque semaine : ce que Rollee dit avoir gagné, et les virements reçus en banque. */
export function RapprochementsRollee({
  etat,
  chauffeurs,
  onChanger,
}: {
  etat: EtatClassees;
  chauffeurs: { id: string; nom: string }[];
  onChanger: (suivant: EtatClassees) => void;
}) {
  const [charge, setCharge] = useState<{
    dossier: string;
    semaines: SemaineRapprochement[];
    manques: string[];
  } | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [filtre, setFiltre] = useState("toutes");
  const [relecture, setRelecture] = useState(0);
  const dossier = etat.chauffeur;
  const semaines = charge?.dossier === dossier ? charge.semaines : null;
  const manques = charge?.dossier === dossier ? charge.manques : [];

  useEffect(() => {
    if (!dossier) return;
    let actif = true;
    Promise.all([lireRapprochementsExpert(dossier), lireManquesRapprochementExpert(dossier)])
      .then(([lues, manquants]) => {
        if (actif) {
          setCharge({ dossier, semaines: lues, manques: manquants });
          setErreur(null);
        }
      })
      .catch((exception: unknown) => {
        if (!actif) return;
        if (exception instanceof ErreurAuthGestionnaire) {
          setErreur("Session expirée.");
          return;
        }
        if (exception instanceof ModeExpertRefuse) {
          // AXE-934 : une entreprise hors de la lettre de mission ne s'affiche pas.
          setErreur(`${exception.message} Ajoutez-la à votre lettre de mission dans Équipe.`);
          return;
        }
        setErreur(messageEchecChargement(exception, "Les rapprochements n'ont pas pu être lus."));
      });
    return () => {
      actif = false;
    };
  }, [dossier, relecture]);

  const affichees = useMemo(
    () => (filtre === "toutes" ? (semaines ?? []) : (semaines ?? []).filter((s) => s.etat === filtre)),
    [filtre, semaines],
  );

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-center gap-2 text-sm text-subtle">
        Entreprise
        <SelectRecherche
          aria-label="Entreprise"
          value={dossier || "aucune"}
          onValueChange={(valeur) => onChanger(changer(etat, "chauffeur", valeur === "aucune" ? "" : valeur))}
          options={[
            { value: "aucune", label: "Choisir" },
            ...chauffeurs.map((chauffeur) => ({ value: chauffeur.id, label: chauffeur.nom })),
          ]}
          className="w-64"
        />
        <Select
          aria-label="État du rapprochement"
          value={filtre}
          onValueChange={setFiltre}
          options={[
            { value: "toutes", label: "Toutes les semaines" },
            ...Object.entries(ETATS).map(([id, libelle]) => ({ value: id, label: libelle })),
          ]}
          className="w-52"
        />
      </div>
      <p className="mt-3 text-sm text-subtle">
        Dû = gagné net moins les courses en espèces. Payé = virements de la plateforme reçus en
        banque. Les frais sont ceux des retraits instantanés.
      </p>
      {!dossier && <p className="mt-6 text-sm text-subtle">Choisissez une entreprise.</p>}
      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
      {dossier && !erreur && semaines === null && (
        <p className="mt-6 text-sm text-subtle" aria-busy="true">
          Chargement des rapprochements…
        </p>
      )}
      {manques.length > 0 && (
        <div className="mt-4 rounded-md border border-warning-border bg-warning-subtle p-3 text-sm text-ink">
          <p className="font-medium">Ce qui manque pour tout rapprocher</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {manques.map((phrase) => (
              <li key={phrase}>{phrase}</li>
            ))}
          </ul>
        </div>
      )}
      {semaines && affichees.length === 0 && (
        <p className="mt-6 text-sm text-subtle">Aucune semaine pour ce filtre.</p>
      )}
      {affichees.length > 0 && (
        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
          {affichees.map((semaine) => (
            <Semaine
              key={`${semaine.plateforme}-${semaine.du}`}
              dossier={dossier}
              semaine={semaine}
              onTranchee={() => setRelecture((n) => n + 1)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Semaine({
  dossier,
  semaine,
  onTranchee,
}: {
  dossier: string;
  semaine: SemaineRapprochement;
  onTranchee: () => void;
}) {
  return (
    <details className="py-3">
      <summary className="cursor-pointer text-sm text-ink">
        <span className="font-medium">{libellePlateforme(semaine.plateforme)}</span>
        <span className="text-subtle">
          {" "}
          · {formatDate(semaine.du)} – {formatDate(semaine.au)} · {ETATS[semaine.etat] ?? semaine.etat}
        </span>
        <span className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
          <Montant libelle="Dû" centimes={semaine.du_cts} />
          <Montant libelle="Payé" centimes={semaine.paye_cts} />
          <Montant libelle="Frais" centimes={semaine.frais_cts} />
          <Montant libelle="Écart" centimes={semaine.ecart_cts} />
        </span>
      </summary>
      {semaine.motif && <p className="mt-2 text-sm text-subtle">{semaine.motif}</p>}
      {semaine.etat === "a_verifier" && (
        <DecisionSemaine dossier={dossier} semaine={semaine} onTranchee={onTranchee} />
      )}
      <Jours jours={semaine.jours} />
      <Virements virements={semaine.virements} />
    </details>
  );
}

/** AXE-912 : la sortie d'une semaine qui ne retombe pas juste seule. */
function DecisionSemaine({
  dossier,
  semaine,
  onTranchee,
}: {
  dossier: string;
  semaine: SemaineRapprochement;
  onTranchee: () => void;
}) {
  const [motif, setMotif] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{ texte: string; erreur: boolean } | null>(null);

  async function decider(decision: "ecrire" | "ecarter") {
    setEnCours(true);
    setMessage(null);
    try {
      const resume = await trancherSemaineExpert(dossier, {
        plateforme: semaine.plateforme,
        lundi: semaine.du,
        decision,
        motif,
      });
      setMessage({ texte: resume, erreur: false });
      onTranchee();
    } catch (exception) {
      setMessage({
        texte: exception instanceof Error ? exception.message : "La décision n'a pas pu être enregistrée.",
        erreur: true,
      });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="mt-3 rounded-md border border-border bg-canvas-app p-3">
      <p className="text-sm text-ink">
        Cette semaine ne retombe pas juste seule. <strong>Écrire telle quelle</strong> passe la recette
        de chaque jour et le solde des virements ; l&apos;écart reste dû par la plateforme, au compte
        de la plateforme. <strong>Écarter</strong> sort ces jours de la comptabilité, sans rien écrire.
      </p>
      <Input
        className="mt-2"
        value={motif}
        onChange={(evenement) => setMotif(evenement.target.value)}
        placeholder="Motif (obligatoire), par ex. commission Uber absente chez Rollee"
        aria-label="Motif de la décision"
      />
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={enCours || !motif.trim()}
          onClick={() => decider("ecrire")}
        >
          Écrire telle quelle
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={enCours || !motif.trim()}
          onClick={() => decider("ecarter")}
        >
          Écarter ces jours
        </Button>
      </div>
      {message && (
        <p className={`mt-2 text-sm ${message.erreur ? "text-danger" : "text-subtle"}`}>{message.texte}</p>
      )}
    </div>
  );
}

function Montant({ libelle, centimes }: { libelle: string; centimes: number }) {
  return (
    <span className="text-sm">
      <span className="text-subtle">{libelle} </span>
      <span className="tabular-nums text-ink">{formatMontant(centimes)}</span>
    </span>
  );
}

function Jours({ jours }: { jours: SemaineRapprochement["jours"] }) {
  if (jours.length === 0) return <p className="mt-3 text-sm text-subtle">Aucun jour Rollee.</p>;
  return (
    <table className="mt-3 w-full text-sm">
      <caption className="mb-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
        Rollee
      </caption>
      <thead>
        <tr className="text-xs text-slate-500">
          <th className="px-2 py-1 text-left font-medium">Jour</th>
          <th className="px-2 py-1 text-right font-medium">Brut</th>
          <th className="px-2 py-1 text-right font-medium">Commission</th>
          <th className="px-2 py-1 text-right font-medium">Espèces</th>
          <th className="px-2 py-1 text-right font-medium">Net</th>
          <th className="px-2 py-1 text-right font-medium">Dû</th>
        </tr>
      </thead>
      <tbody>
        {jours.map((jour) => (
          <tr key={jour.date} className="border-t border-slate-100">
            <td className="px-2 py-1">{formatDate(jour.date)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.brut_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.commission_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.especes_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.net_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.du_cts)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Virements({ virements }: { virements: SemaineRapprochement["virements"] }) {
  if (virements.length === 0) return <p className="mt-3 text-sm text-subtle">Aucun virement en banque.</p>;
  return (
    <table className="mt-3 w-full text-sm">
      <caption className="mb-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
        Banque
      </caption>
      <thead>
        <tr className="text-xs text-slate-500">
          <th className="px-2 py-1 text-left font-medium">Date</th>
          <th className="px-2 py-1 text-left font-medium">Libellé</th>
          <th className="px-2 py-1 text-left font-medium">Nature</th>
          <th className="px-2 py-1 text-left font-medium">Compte</th>
          <th className="px-2 py-1 text-right font-medium">Montant</th>
        </tr>
      </thead>
      <tbody>
        {virements.map((virement) => (
          <tr key={`${virement.date}-${virement.libelle}-${virement.montant_cts}`} className="border-t border-slate-100">
            <td className="px-2 py-1">{formatDate(virement.date)}</td>
            <td className="px-2 py-1">{virement.libelle}</td>
            <td className="px-2 py-1">{NATURES[virement.nature] ?? virement.nature}</td>
            <td className="px-2 py-1 tabular-nums">{virement.compte}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(virement.montant_cts)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function libellePlateforme(nom: string): string {
  return nom ? nom.charAt(0).toUpperCase() + nom.slice(1) : nom;
}
