"use client";

import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/Badge";
import { FicheWebhookRollee } from "@/components/FicheWebhookRollee";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  ajouterBranchement,
  listerBranchements,
  modifierBranchement,
  testerBranchement,
  type Branchement,
} from "@/lib/auth-gestionnaire";
import { TYPES_BRANCHEMENT } from "@/lib/branchements";
import { formatDate } from "@/lib/format";

type ResultatAction = Branchement[] | string | { message: string; liste: Branchement[] };

function message(exception: unknown, defaut: string): string {
  return exception instanceof Error ? exception.message : defaut;
}

function comparer(a: Branchement, b: Branchement): number {
  if (a.par_defaut !== b.par_defaut) return a.par_defaut ? -1 : 1;
  if (a.actif !== b.actif) return a.actif ? -1 : 1;
  return a.nom.localeCompare(b.nom, "fr");
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
  const [infoEphemere, setInfoEphemere] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const tries = [...branchements].sort(comparer);

  useEffect(() => {
    if (!info || !infoEphemere) return;
    const delai = window.setTimeout(() => setInfo(null), 3000);
    return () => window.clearTimeout(delai);
  }, [info, infoEphemere]);

  async function agir(action: () => Promise<ResultatAction>) {
    setEnCours(true);
    setInfo(null);
    try {
      const resultat = await action();
      if (typeof resultat === "string") {
        setInfoEphemere(true);
        setInfo(resultat);
      } else if (Array.isArray(resultat)) {
        setInfoEphemere(false);
        onChange(resultat);
        setEdition(null);
      } else {
        setInfoEphemere(true);
        setInfo(resultat.message);
        onChange(resultat.liste);
        setEdition(null);
      }
    } catch (exception) {
      setInfoEphemere(false);
      setInfo(message(exception, "L'opération n'a pas abouti."));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="rounded-lg border border-border bg-canvas">
      <header className="flex items-start justify-between gap-4 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">{config.nom}</h2>
          <p className="mt-1 text-sm text-subtle">{config.detail}</p>
        </div>
        {admin && edition?.mode !== "ajout" && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="shrink-0"
            onClick={() => setEdition({ mode: "ajout" })}
          >
            Ajouter
          </Button>
        )}
      </header>
      {tries.length > 0 && (
        <ul className="divide-y divide-hairline border-t border-hairline">
          {tries.map((b) => (
            <LigneBranchement
              key={b.id}
              branchement={b}
              admin={admin}
              enCours={enCours}
              edition={edition}
              setEdition={setEdition}
              agir={agir}
              recharger={() => {
                void listerBranchements().then(onChange);
              }}
            />
          ))}
        </ul>
      )}
      {tries.length === 0 && edition?.mode !== "ajout" && (
        <p className="border-t border-hairline px-5 py-4 text-sm text-subtle">Aucun accès.</p>
      )}
      {edition?.mode === "ajout" && (
        <div className="border-t border-hairline px-5 py-4">
          <FormulaireBranchement
            type={type}
            avecNom
            enCours={enCours}
            onAnnuler={() => setEdition(null)}
            onValider={(nom, parametres) =>
              agir(() => ajouterBranchement(type, config.fournisseur, nom, parametres))
            }
          />
        </div>
      )}
      {info && (
        <p role="status" className="border-t border-hairline px-5 py-3 text-sm text-subtle">
          {info}
        </p>
      )}
    </section>
  );
}

function LigneBranchement({
  branchement: b,
  admin,
  enCours,
  edition,
  setEdition,
  agir,
  recharger,
}: {
  branchement: Branchement;
  admin: boolean;
  enCours: boolean;
  edition: Edition;
  setEdition: (edition: Edition) => void;
  agir: (action: () => Promise<ResultatAction>) => Promise<void>;
  recharger: () => void;
}) {
  const [relier, setRelier] = useState(false);
  const enEdition = edition !== null && edition.mode !== "ajout" && edition.id === b.id;
  const actions = [
    {
      libelle: "Renommer",
      onSelect: () => setEdition({ mode: "nom", id: b.id }),
    },
    {
      libelle: "Changer les identifiants",
      onSelect: () => setEdition({ mode: "identifiants", id: b.id }),
    },
    ...(b.type !== "rollee" && b.actif && !b.par_defaut
      ? [
          {
            libelle: "Utiliser par défaut",
            onSelect: () => agir(() => modifierBranchement(b.id, { par_defaut: true })),
          },
        ]
      : []),
    {
      libelle: b.actif ? "Désactiver" : "Réactiver",
      onSelect: () => agir(() => modifierBranchement(b.id, { actif: !b.actif })),
    },
  ];

  return (
    <li className={b.par_defaut && b.type !== "rollee" ? "bg-canvas-app" : undefined}>
      <div className="flex items-center gap-3 px-5 py-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <span className={`truncate text-sm font-medium ${b.actif ? "text-ink" : "text-subtle"}`}>
            {b.nom}
          </span>
          {b.par_defaut && b.type !== "rollee" && <Badge variant="neutral">Par défaut</Badge>}
          {!b.actif && <Badge variant="closed">Désactivé</Badge>}
          {b.type === "rollee" && b.secrets.includes("secret_webhook") && (
            <Badge variant="neutral">Webhook prêt</Badge>
          )}
        </div>
        {b.secrets.length > 0 && (
          <span className="hidden shrink-0 text-xs text-subtle sm:block">Masqué</span>
        )}
        {b.maj_le && (
          <span className="hidden shrink-0 text-xs text-subtle sm:block">
            Réglé le {formatDate(b.maj_le.slice(0, 10))}
          </span>
        )}
        {admin && !enEdition && (
          <>
            {b.type === "rollee" && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={enCours}
                onClick={() => setRelier(true)}
              >
                {b.secrets.includes("secret_webhook") ? "Voir le webhook" : "Relier"}
              </Button>
            )}
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
            <MenuActions enCours={enCours} actions={actions} />
          </>
        )}
      </div>
      {relier && (
        <FicheWebhookRollee id={b.id} onFermer={() => setRelier(false)} onPrepare={recharger} />
      )}
      {enEdition && edition.mode === "nom" && (
        <div className="px-5 pb-3">
          <Renommer
            nom={b.nom}
            enCours={enCours}
            onAnnuler={() => setEdition(null)}
            onValider={(nom) => agir(() => modifierBranchement(b.id, { nom }))}
          />
        </div>
      )}
      {enEdition && edition.mode === "identifiants" && (
        <div className="px-5 pb-4">
          <FormulaireBranchement
            type={b.type}
            avecNom={false}
            enCours={enCours}
            existant={{ champs: b.champs, secrets: b.secrets }}
            onAnnuler={() => setEdition(null)}
            onValider={(_nom, parametres) =>
              agir(() => modifierBranchement(b.id, { parametres }))
            }
          />
        </div>
      )}
    </li>
  );
}

function MenuActions({
  enCours,
  actions,
}: {
  enCours: boolean;
  actions: { libelle: string; onSelect: () => void | Promise<void> }[];
}) {
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ouvert) return;
    function fermerAuClic(evenement: MouseEvent) {
      if (!zone.current?.contains(evenement.target as Node)) setOuvert(false);
    }
    function fermerAuClavier(evenement: KeyboardEvent) {
      if (evenement.key === "Escape") setOuvert(false);
    }
    document.addEventListener("mousedown", fermerAuClic);
    document.addEventListener("keydown", fermerAuClavier);
    return () => {
      document.removeEventListener("mousedown", fermerAuClic);
      document.removeEventListener("keydown", fermerAuClavier);
    };
  }, [ouvert]);

  return (
    <div className={`relative shrink-0 ${ouvert ? "z-20" : ""}`} ref={zone}>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={ouvert}
        disabled={enCours}
        onClick={() => setOuvert((etat) => !etat)}
      >
        Actions
      </Button>
      {ouvert && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-56 rounded-md border border-border bg-canvas py-1 shadow-sm"
        >
          {actions.map((action) => (
            <button
              key={action.libelle}
              type="button"
              role="menuitem"
              className="block w-full px-3 py-1.5 text-left text-sm text-ink hover:bg-surface-soft"
              onClick={() => {
                setOuvert(false);
                void action.onSelect();
              }}
            >
              {action.libelle}
            </button>
          ))}
        </div>
      )}
    </div>
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
      className="flex max-w-md gap-2"
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

function SaisieSecrete({
  value,
  onChange,
  required,
  dejaEnregistre,
}: {
  value: string;
  onChange: (valeur: string) => void;
  required: boolean;
  dejaEnregistre: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <Input
      type={visible ? "text" : "password"}
      required={required}
      autoComplete="new-password"
      spellCheck={false}
      value={value}
      placeholder={dejaEnregistre ? "Retaper pour remplacer" : undefined}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      onChange={(e) => onChange(e.target.value)}
      className="mt-1"
    />
  );
}

function FormulaireBranchement({
  type,
  avecNom,
  enCours,
  existant,
  onAnnuler,
  onValider,
}: {
  type: Branchement["type"];
  avecNom: boolean;
  enCours: boolean;
  existant?: { champs: Record<string, string>; secrets: string[] };
  onAnnuler: () => void;
  onValider: (nom: string, parametres: Record<string, string>) => void;
}) {
  const config = TYPES_BRANCHEMENT[type];
  const [nom, setNom] = useState("");
  const [valeurs, setValeurs] = useState<Record<string, string>>(existant?.champs ?? {});
  return (
    <form
      className="space-y-3"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        onValider(nom, valeurs);
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {avecNom && (
          <label className="block text-sm text-ink sm:col-span-2">
            Nom, pour le reconnaître
            <Input
              required
              placeholder={`${config.nom} agence Nord`}
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              className="mt-1"
            />
          </label>
        )}
        {config.champs.map((champ) => {
          const dejaEnregistre = existant?.secrets.includes(champ.cle) ?? false;
          return (
            <label key={champ.cle} className="block text-sm text-ink">
              {champ.libelle}
              {champ.secret ? (
                <SaisieSecrete
                  value={valeurs[champ.cle] ?? ""}
                  required={!champ.facultatif && !dejaEnregistre}
                  dejaEnregistre={dejaEnregistre}
                  onChange={(valeur) => setValeurs((v) => ({ ...v, [champ.cle]: valeur }))}
                />
              ) : champ.type === "choix" ? (
                <Select
                  aria-label={champ.libelle}
                  value={valeurs[champ.cle] ?? ""}
                  placeholder="Choisir…"
                  onValueChange={(valeur) => setValeurs((v) => ({ ...v, [champ.cle]: valeur }))}
                  options={(champ.options ?? []).map((option) => ({
                    value: option.valeur,
                    label: option.libelle,
                  }))}
                  className="mt-1"
                />
              ) : (
                <Input
                  type={champ.type}
                  required={!champ.facultatif}
                  autoComplete="off"
                  value={valeurs[champ.cle] ?? ""}
                  onChange={(e) => setValeurs((v) => ({ ...v, [champ.cle]: e.target.value }))}
                  className="mt-1"
                />
              )}
            </label>
          );
        })}
      </div>
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
