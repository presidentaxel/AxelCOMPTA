"use client";

import { useState } from "react";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ajouterBranchement,
  modifierBranchement,
  testerBranchement,
  type Branchement,
} from "@/lib/auth-gestionnaire";
import { TYPES_BRANCHEMENT } from "@/lib/branchements";
import { formatDate } from "@/lib/format";

type Edition =
  { mode: "ajout" } | { mode: "identifiants" | "nom"; id: string } | null;

function message(exception: unknown, defaut: string): string {
  return exception instanceof Error ? exception.message : defaut;
}

/** AXE-872 : les branchements d'un type (plusieurs SMTP, plusieurs comptes
 * Digifactory…). Un seul par défaut ; chaque entreprise peut en choisir un
 * autre depuis sa fiche. Les identifiants ne reviennent jamais à l'écran. */
export function BranchementsType({
  type,
  branchements,
  admin,
  onChange,
}: {
  type: Branchement["type"];
  branchements: Branchement[];
  admin: boolean;
  onChange: (liste: Branchement[]) => void;
}) {
  const config = TYPES_BRANCHEMENT[type];
  const [edition, setEdition] = useState<Edition>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function agir(action: () => Promise<Branchement[] | string>) {
    setEnCours(true);
    setInfo(null);
    try {
      const resultat = await action();
      if (typeof resultat === "string") setInfo(resultat);
      else {
        onChange(resultat);
        setEdition(null);
      }
    } catch (exception) {
      setInfo(message(exception, "L'opération n'a pas abouti."));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <li className="border-b border-hairline py-4">
      <div className="flex items-start justify-between gap-6">
        <span>
          <span className="block text-sm font-medium text-ink">
            {config.nom}
          </span>
          <span className="mt-1 block text-sm text-subtle">
            {config.detail}
          </span>
        </span>
        {branchements.length === 0 && (
          <span className="shrink-0 text-xs text-subtle">À brancher</span>
        )}
      </div>
      {branchements.length > 0 && (
        <ul className="mt-3 space-y-3">
          {branchements.map((b) => (
            <LigneBranchement
              key={b.id}
              branchement={b}
              admin={admin}
              enCours={enCours}
              edition={edition}
              setEdition={setEdition}
              agir={agir}
            />
          ))}
        </ul>
      )}
      {admin && edition?.mode !== "ajout" && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => setEdition({ mode: "ajout" })}
        >
          {branchements.length === 0
            ? "Brancher"
            : `Ajouter un autre accès ${config.nom}`}
        </Button>
      )}
      {edition?.mode === "ajout" && (
        <FormulaireBranchement
          type={type}
          avecNom
          enCours={enCours}
          onAnnuler={() => setEdition(null)}
          onValider={(nom, parametres) =>
            agir(() =>
              ajouterBranchement(type, config.fournisseur, nom, parametres),
            )
          }
        />
      )}
      {info && <p className="mt-2 text-sm text-subtle">{info}</p>}
    </li>
  );
}

function LigneBranchement({
  branchement: b,
  admin,
  enCours,
  edition,
  setEdition,
  agir,
}: {
  branchement: Branchement;
  admin: boolean;
  enCours: boolean;
  edition: Edition;
  setEdition: (edition: Edition) => void;
  agir: (action: () => Promise<Branchement[] | string>) => Promise<void>;
}) {
  const enEdition =
    edition !== null && edition.mode !== "ajout" && edition.id === b.id;
  return (
    <li className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`text-sm font-medium ${b.actif ? "text-ink" : "text-subtle"}`}
        >
          {b.nom}
        </span>
        {b.par_defaut && <Badge variant="neutral">Par défaut</Badge>}
        {!b.actif && <Badge variant="closed">Désactivé</Badge>}
        {b.maj_le && (
          <span className="text-xs text-subtle">
            Réglé le {formatDate(b.maj_le.slice(0, 10))}
          </span>
        )}
      </div>
      {admin && !enEdition && (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={enCours}
            onClick={() =>
              agir(async () => {
                const essai = await testerBranchement(b.id);
                return `${b.nom} : ${essai.message}`;
              })
            }
          >
            Tester
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setEdition({ mode: "nom", id: b.id })}
          >
            Renommer
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setEdition({ mode: "identifiants", id: b.id })}
          >
            Changer les identifiants
          </Button>
          {b.actif && !b.par_defaut && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={enCours}
              onClick={() =>
                agir(() => modifierBranchement(b.id, { par_defaut: true }))
              }
            >
              Utiliser par défaut
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={enCours}
            onClick={() =>
              agir(() => modifierBranchement(b.id, { actif: !b.actif }))
            }
          >
            {b.actif ? "Désactiver" : "Réactiver"}
          </Button>
        </div>
      )}
      {enEdition && edition.mode === "nom" && (
        <Renommer
          nom={b.nom}
          enCours={enCours}
          onAnnuler={() => setEdition(null)}
          onValider={(nom) => agir(() => modifierBranchement(b.id, { nom }))}
        />
      )}
      {enEdition && edition.mode === "identifiants" && (
        <FormulaireBranchement
          type={b.type}
          avecNom={false}
          enCours={enCours}
          onAnnuler={() => setEdition(null)}
          onValider={(_nom, parametres) =>
            agir(() => modifierBranchement(b.id, { parametres }))
          }
        />
      )}
    </li>
  );
}

function Renommer({
  nom,
  enCours,
  onAnnuler,
  onValider,
}: {
  nom: string;
  enCours: boolean;
  onAnnuler: () => void;
  onValider: (nom: string) => void;
}) {
  const [valeur, setValeur] = useState(nom);
  return (
    <form
      className="mt-2 flex gap-2"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        onValider(valeur);
      }}
    >
      <Input
        aria-label="Nouveau nom"
        required
        value={valeur}
        onChange={(e) => setValeur(e.target.value)}
      />
      <Button type="submit" size="sm" disabled={enCours}>
        Enregistrer
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={onAnnuler}>
        Annuler
      </Button>
    </form>
  );
}

function FormulaireBranchement({
  type,
  avecNom,
  enCours,
  onAnnuler,
  onValider,
}: {
  type: Branchement["type"];
  avecNom: boolean;
  enCours: boolean;
  onAnnuler: () => void;
  onValider: (nom: string, parametres: Record<string, string>) => void;
}) {
  const config = TYPES_BRANCHEMENT[type];
  const [nom, setNom] = useState("");
  const [valeurs, setValeurs] = useState<Record<string, string>>({});
  return (
    <form
      className="mt-3 space-y-2"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        onValider(nom, valeurs);
      }}
    >
      {avecNom && (
        <label className="block text-sm text-ink">
          Nom (pour le reconnaître, par exemple « {config.nom} agence Nord »)
          <Input
            required
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            className="mt-1"
          />
        </label>
      )}
      {config.champs.map((champ) => (
        <label key={champ.cle} className="block text-sm text-ink">
          {champ.libelle}
          <Input
            type={champ.type}
            required={!champ.facultatif}
            autoComplete="off"
            value={valeurs[champ.cle] ?? ""}
            onChange={(e) =>
              setValeurs((v) => ({ ...v, [champ.cle]: e.target.value }))
            }
            className="mt-1"
          />
        </label>
      ))}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={enCours}>
          {enCours ? "Enregistrement…" : "Enregistrer"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onAnnuler}>
          Annuler
        </Button>
      </div>
    </form>
  );
}
