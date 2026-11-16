"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { habiliterExpert, listerDossiers, listerExperts, type ExpertDeclare } from "@/lib/auth-gestionnaire";
import type { DossierAgregat } from "@/lib/types";

const VIDE = { email: "", nom: "", cabinet: "", numero_ordre: "", lettre_mission: "", date_lettre: "" };
type Champs = typeof VIDE;

/** AXE-800, AXE-945 : les experts-comptables du portefeuille et les dossiers
 * couverts par leur lettre de mission. Un admin en déclare un, ou modifie la
 * déclaration d'un expert : le formulaire part de celle en vigueur. Une
 * nouvelle déclaration remplace la précédente, rien ne s'efface, et
 * l'engagement déjà accepté reste valable. */
export function ExpertsDeclares({ admin }: { admin: boolean }) {
  const [experts, setExperts] = useState<ExpertDeclare[] | null>(null);
  const [dossiers, setDossiers] = useState<DossierAgregat[]>([]);
  const [edite, setEdite] = useState<ExpertDeclare | "nouveau" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const charger = useCallback(() => {
    listerExperts()
      .then(setExperts)
      .catch(() => setExperts([]));
  }, []);
  useEffect(() => {
    charger();
    listerDossiers()
      .then(setDossiers)
      .catch(() => setDossiers([]));
  }, [charger]);

  const noms = useMemo(() => new Map(dossiers.map((d) => [d.dossier_id, d.nom])), [dossiers]);

  return (
    <section className="mt-10 space-y-4" aria-labelledby="titre-experts">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="titre-experts" className="text-base font-semibold text-ink">
            Experts-comptables
          </h2>
          <p className="text-sm text-subtle">
            Seul l&apos;expert-comptable habilité voit le détail des dossiers de sa lettre de mission et y
            écrit, sous sa responsabilité. Un admin peut se déclarer lui-même : il garde son rôle d&apos;admin.
          </p>
        </div>
        {admin && edite === null && (
          <Button variant="secondary" onClick={() => setEdite("nouveau")}>
            Déclarer un expert-comptable
          </Button>
        )}
      </div>
      {message && <p role="status" className="text-sm text-ink">{message}</p>}
      {edite !== null && (
        <FormulaireHabilitation
          initial={edite === "nouveau" ? null : edite}
          dossiers={dossiers}
          onAnnuler={() => setEdite(null)}
          onFait={(texte) => {
            setEdite(null);
            setMessage(texte);
            charger();
          }}
        />
      )}
      {experts !== null && experts.length === 0 && edite === null && (
        <p className="text-sm text-subtle">Aucun expert-comptable déclaré.</p>
      )}
      <ul className="space-y-3">
        {(experts ?? []).map((expert) => (
          <li key={expert.email}>
            <CarteExpert
              expert={expert}
              noms={noms}
              total={dossiers.length}
              admin={admin && edite === null}
              onModifier={() => {
                setMessage(null);
                setEdite(expert);
              }}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

function CarteExpert({
  expert,
  noms,
  total,
  admin,
  onModifier,
}: {
  expert: ExpertDeclare;
  noms: Map<string, string>;
  total: number;
  admin: boolean;
  onModifier: () => void;
}) {
  const couverts = expert.dossiers.map((id) => noms.get(id) ?? id).sort((a, b) => a.localeCompare(b));
  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-ink">
            {expert.nom} <span className="font-normal text-subtle">· {expert.cabinet}</span>
          </p>
          <p className="text-sm text-subtle">
            {expert.email} · Ordre n° {expert.numero_ordre} · lettre de mission {expert.lettre_mission} du{" "}
            {new Date(expert.date_lettre).toLocaleDateString("fr-FR")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={expert.engagement_accepte ? "validated" : "pending"}>
            {expert.engagement_accepte ? "Engagement accepté" : "Engagement à accepter"}
          </Badge>
          {admin && (
            <Button size="sm" variant="secondary" onClick={onModifier}>
              Modifier les accès
            </Button>
          )}
        </div>
      </div>
      <p className="text-sm text-ink">
        {couverts.length} dossier{couverts.length > 1 ? "s" : ""} couvert{couverts.length > 1 ? "s" : ""}
        {total > 0 && <span className="text-subtle"> sur {total}</span>}
        {couverts.length > 0 && <span className="text-subtle"> : {couverts.join(", ")}</span>}
      </p>
    </Card>
  );
}

function FormulaireHabilitation({
  initial,
  dossiers,
  onAnnuler,
  onFait,
}: {
  initial: ExpertDeclare | null;
  dossiers: DossierAgregat[];
  onAnnuler: () => void;
  onFait: (message: string) => void;
}) {
  const [champs, setChamps] = useState<Champs>(
    initial
      ? {
          email: initial.email,
          nom: initial.nom,
          cabinet: initial.cabinet,
          numero_ordre: initial.numero_ordre,
          lettre_mission: initial.lettre_mission,
          date_lettre: initial.date_lettre,
        }
      : VIDE,
  );
  const [couverts, setCouverts] = useState<string[]>(initial?.dossiers ?? []);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function envoyer(evenement: React.FormEvent) {
    evenement.preventDefault();
    if (couverts.length === 0) {
      setErreur("Cochez au moins un dossier de la lettre de mission.");
      return;
    }
    setEnvoi(true);
    setErreur(null);
    try {
      const faite = await habiliterExpert({ ...champs, dossiers: couverts });
      onFait(
        initial
          ? `Accès de ${faite.nom} modifiés : ${faite.dossiers.length} dossier(s).`
          : `${faite.nom} est habilité(e) sur ${faite.dossiers.length} dossier(s). Il ou elle acceptera l'engagement de responsabilité à sa première visite du mode expert.`,
      );
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec de l'habilitation.");
    } finally {
      setEnvoi(false);
    }
  }

  const libelles: [keyof Champs, string, string][] = [
    ["email", "E-mail", "email"],
    ["nom", "Nom et prénom", "text"],
    ["cabinet", "Cabinet", "text"],
    ["numero_ordre", "N° d'inscription à l'Ordre", "text"],
    ["lettre_mission", "Référence de la lettre de mission", "text"],
    ["date_lettre", "Date de la lettre de mission", "date"],
  ];

  return (
    <Card>
      <form onSubmit={envoyer} className="space-y-5" aria-labelledby="titre-habilitation">
        <p id="titre-habilitation" className="font-medium text-ink">
          {initial ? `Modifier les accès de ${initial.nom}` : "Déclarer un expert-comptable"}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {libelles.map(([nom, libelle, type]) => (
            <label key={nom} className="block text-sm text-ink">
              {libelle}
              <Input
                type={type}
                required
                value={champs[nom]}
                readOnly={nom === "email" && initial !== null}
                onChange={(e) => setChamps((actuel) => ({ ...actuel, [nom]: e.target.value }))}
                disabled={envoi}
                className="mt-1"
              />
            </label>
          ))}
        </div>
        <ChoixDossiers dossiers={dossiers} couverts={couverts} onChange={setCouverts} desactive={envoi} />
        {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
        <div className="flex gap-2">
          <Button type="submit" disabled={envoi}>
            {envoi ? "Enregistrement…" : initial ? "Enregistrer les accès" : "Habiliter"}
          </Button>
          <Button type="button" variant="ghost" onClick={onAnnuler} disabled={envoi}>
            Annuler
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ChoixDossiers({
  dossiers,
  couverts,
  onChange,
  desactive,
}: {
  dossiers: DossierAgregat[];
  couverts: string[];
  onChange: (couverts: string[]) => void;
  desactive: boolean;
}) {
  const [filtre, setFiltre] = useState("");
  const visibles = dossiers
    .filter((d) => d.nom.toLowerCase().includes(filtre.trim().toLowerCase()))
    .sort((a, b) => a.nom.localeCompare(b.nom));
  const tous = dossiers.length > 0 && couverts.length === dossiers.length;

  return (
    <fieldset className="space-y-2 text-sm text-ink">
      <legend className="font-medium">
        Dossiers couverts{" "}
        <span className="font-normal text-subtle">
          · {couverts.length} sur {dossiers.length}
        </span>
      </legend>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="Chercher un dossier"
          placeholder="Chercher un dossier"
          value={filtre}
          onChange={(e) => setFiltre(e.target.value)}
          className="max-w-xs"
        />
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={desactive}
          onClick={() => onChange(tous ? [] : dossiers.map((d) => d.dossier_id))}
        >
          {tous ? "Tout décocher" : "Tout cocher"}
        </Button>
      </div>
      <ul className="grid max-h-72 gap-1 overflow-y-auto rounded-md border border-border p-2 sm:grid-cols-2">
        {visibles.map((dossier) => (
          <li key={dossier.dossier_id}>
            <label className="flex items-center gap-2 rounded px-2 py-1 hover:bg-surface-soft">
              <input
                type="checkbox"
                disabled={desactive}
                checked={couverts.includes(dossier.dossier_id)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...couverts, dossier.dossier_id]
                      : couverts.filter((id) => id !== dossier.dossier_id),
                  )
                }
              />
              {dossier.nom}
            </label>
          </li>
        ))}
        {visibles.length === 0 && <li className="px-2 py-1 text-subtle">Aucun dossier ne correspond.</li>}
      </ul>
    </fieldset>
  );
}
