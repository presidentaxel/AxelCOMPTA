"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Aide, POURQUOI_RIEN_N_EST_ENVOYE } from "@/components/Aide";
import { BoutonChoix } from "@/components/BoutonChoix";
import { ConfirmationDialogue, type Confirmation } from "@/components/ConfirmationDialogue";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  creerRegle,
  ErreurAuthGestionnaire,
  listerDossiers,
  listerRegles,
  modifierRegle,
  supprimerRegle,
  type RegleRappel,
} from "@/lib/auth-gestionnaire";
import type { DossierAgregat } from "@/lib/types";
import { useDroitGestionnaire } from "@/lib/use-droit";

const CANAUX = [
  { id: "sms", libelle: "SMS" },
  { id: "mail", libelle: "E-mail" },
  { id: "appel", libelle: "Appel" },
];

function libelleCanal(id: string): string {
  return CANAUX.find((canal) => canal.id === id)?.libelle ?? id;
}

/** Réglages. Une règle « avant clôture » part seule pour les entreprises
 * concernées. L'envoi réel attend le branchement du canal. */
/** AXE-890 : message proposé pour relancer un chauffeur sans plateforme reliée. */
const MESSAGE_PLATEFORMES =
  "Reliez vos comptes Uber et Bolt dans Compte › Mes plateformes : vos recettes seront détaillées automatiquement.";

export default function RappelsPage() {
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const [regles, setRegles] = useState<RegleRappel[] | null>(null);
  const [dossiers, setDossiers] = useState<DossierAgregat[]>([]);
  const [libelle, setLibelle] = useState("");
  const [message, setMessage] = useState("");
  const [canaux, setCanaux] = useState<string[]>(["mail"]);
  const [declencheur, setDeclencheur] = useState("avant_cloture");
  const [jours, setJours] = useState("15");
  const [portee, setPortee] = useState("tous");
  const [choisis, setChoisis] = useState<string[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [erreurRegle, setErreurRegle] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

  useEffect(() => {
    listerRegles()
      .then(setRegles)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur("Impossible de charger les rappels.");
      });
    listerDossiers()
      .then(setDossiers)
      .catch(() => undefined);
  }, [router]);

  async function ajouter(regle: {
    libelle: string;
    message: string;
    canaux: string[];
    declencheur: string;
    jours_avant: number | null;
    portee?: string;
    dossier_ids?: string[];
  }) {
    if (regle.declencheur !== "manuel" && (!regle.jours_avant || regle.jours_avant < 1)) {
      setErreur("Indiquez un nombre de jours supérieur à zéro.");
      return;
    }
    if (regle.portee === "selection" && (regle.dossier_ids?.length ?? 0) === 0) {
      setErreur("Choisissez au moins une entreprise.");
      return;
    }
    setEnCours(true);
    setErreur(null);
    try {
      await creerRegle(regle);
      setLibelle("");
      setMessage("");
      setRegles(await listerRegles());
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec de l'enregistrement.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div>
      <h1 className="text-[22px] font-bold tracking-tight text-ink">Rappels</h1>
      <p className="mt-2 text-sm text-subtle">
        Les relances se préparent ici. L&apos;envoi n&apos;est pas branché : aucun SMS, e-mail ou appel ne part.
        <Aide texte={POURQUOI_RIEN_N_EST_ENVOYE} />
      </p>

      <div className="mt-8 grid items-start gap-8 lg:grid-cols-3">
      <form
        className="space-y-4 lg:col-span-2"
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (!droit.admin) return;
          void ajouter({
            libelle: libelle.trim(),
            message: message.trim(),
            canaux,
            declencheur,
            jours_avant: declencheur !== "manuel" ? Number(jours) : null,
            portee,
            dossier_ids: choisis,
          });
        }}
      >
        <p className="text-sm font-medium text-ink">Votre règle</p>
        {!droit.admin && (
          <p className="text-sm text-subtle">
            Seule une personne administratrice crée ou modifie une règle.
          </p>
        )}
        <Input
          value={libelle}
          onChange={(e) => setLibelle(e.target.value)}
          placeholder="Nom"
          aria-label="Nom de la règle"
          required
          disabled={enCours || !droit.admin}
        />
        <Input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Message"
          aria-label="Message de la règle"
          required
          disabled={enCours || !droit.admin}
        />
        <div className="flex flex-wrap gap-2">
          {CANAUX.map((canal) => {
            const actif = canaux.includes(canal.id);
            return (
              <BoutonChoix
                key={canal.id}
                actif={actif}
                disabled={!droit.admin}
                onClick={() =>
                  setCanaux((actuel) => (actif ? actuel.filter((id) => id !== canal.id) : [...actuel, canal.id]))
                }
              >
                {canal.libelle}
              </BoutonChoix>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <BoutonChoix actif={declencheur === "avant_cloture"} disabled={!droit.admin} onClick={() => setDeclencheur("avant_cloture")}>
            Avant la clôture
          </BoutonChoix>
          <BoutonChoix actif={declencheur === "a_traiter"} disabled={!droit.admin} onClick={() => setDeclencheur("a_traiter")}>
            Opérations en attente
          </BoutonChoix>
          <BoutonChoix
            actif={declencheur === "plateformes_non_reliees"}
            disabled={!droit.admin}
            onClick={() => {
              setDeclencheur("plateformes_non_reliees");
              if (!message.trim()) setMessage(MESSAGE_PLATEFORMES);
            }}
          >
            Plateformes non reliées
          </BoutonChoix>
          <BoutonChoix actif={declencheur === "manuel"} disabled={!droit.admin} onClick={() => setDeclencheur("manuel")}>
            Bouton sur la fiche
          </BoutonChoix>
          {declencheur !== "manuel" && (
            <label className="flex items-center gap-2 text-subtle">
              {declencheur === "a_traiter" && "depuis"}
              {declencheur === "plateformes_non_reliees" && "tous les"}
              <Input
                value={jours}
                onChange={(e) => setJours(e.target.value)}
                inputMode="numeric"
                className="w-16"
                aria-label={
                  declencheur === "a_traiter"
                    ? "Jours d'attente"
                    : declencheur === "plateformes_non_reliees"
                      ? "Jours entre deux rappels"
                      : "Jours avant la clôture"
                }
              />
              {declencheur === "avant_cloture" ? "jours avant" : "jours"}
            </label>
          )}
        </div>
        <div className="flex gap-2">
          <BoutonChoix actif={portee === "tous"} disabled={!droit.admin} onClick={() => setPortee("tous")}>
            Toutes les entreprises
          </BoutonChoix>
          <BoutonChoix actif={portee === "selection"} disabled={!droit.admin} onClick={() => setPortee("selection")}>
            Certaines
          </BoutonChoix>
        </div>
        {portee === "selection" && (
          <ul className="max-h-40 overflow-y-auto rounded-md border border-border">
            {dossiers.map((dossier) => (
              <li key={dossier.dossier_id}>
                <label className="flex items-center gap-2 px-3 py-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={choisis.includes(dossier.dossier_id)}
                    onChange={() =>
                      setChoisis((actuel) =>
                        actuel.includes(dossier.dossier_id)
                          ? actuel.filter((id) => id !== dossier.dossier_id)
                          : [...actuel, dossier.dossier_id],
                      )
                    }
                  />
                  {dossier.nom}
                </label>
              </li>
            ))}
          </ul>
        )}
        {erreur && <p className="text-sm text-danger">{erreur}</p>}
        <Button type="submit" disabled={!droit.admin || enCours || canaux.length === 0}>
          Enregistrer la règle
        </Button>
      </form>
      <div>
      <p className="text-sm font-medium text-ink">Règles</p>
      {erreurRegle && <p className="mt-3 text-sm text-danger">{erreurRegle}</p>}
      <ul className="mt-3">
        {regles?.map((regle) => (
          <li key={regle.id} className="border-b border-hairline py-4">
            <p className="text-sm font-medium text-ink">{regle.libelle}</p>
            <p className="mt-1 text-sm text-subtle">{regle.message}</p>
            {droit.admin && (
              <div className="mt-2 flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    setErreurRegle(null);
                    try {
                      await modifierRegle(regle.id, { actif: !regle.actif });
                      setRegles(await listerRegles());
                    } catch (exception) {
                      setErreurRegle(
                        exception instanceof Error ? exception.message : "Impossible de modifier la règle.",
                      );
                    }
                  }}
                >
                  {regle.actif ? "Suspendre" : "Activer"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setConfirmation({
                      titre: "Supprimer la règle",
                      phrase: `Supprimer la règle « ${regle.libelle} » ? Elle ne se déclenchera plus.`,
                      libelleConfirmer: "Supprimer",
                      destructive: true,
                      onConfirmer: async () => {
                        setErreurRegle(null);
                        try {
                          await supprimerRegle(regle.id);
                          setRegles(await listerRegles());
                        } catch (exception) {
                          setErreurRegle(
                            exception instanceof Error ? exception.message : "Impossible de supprimer la règle.",
                          );
                        }
                      },
                    })
                  }
                >
                  Supprimer
                </Button>
              </div>
            )}
            <p className="mt-1 text-xs text-subtle">
              {regle.declencheur === "avant_cloture"
                ? `${regle.jours_avant} jours avant la clôture`
                : regle.declencheur === "a_traiter"
                  ? `Opérations en attente depuis ${regle.jours_avant} jours`
                  : regle.declencheur === "plateformes_non_reliees"
                    ? `Plateformes non reliées, tous les ${regle.jours_avant} jours`
                    : "Bouton sur la fiche"}
              {" · "}
              {regle.portee === "selection" ? `${regle.dossier_ids.length} entreprise(s)` : "Toutes"}
              {" · "}
              {regle.actif ? "Active" : "Suspendue"}
              {" · Envoi non branché"}
              <Aide texte={POURQUOI_RIEN_N_EST_ENVOYE} />
              {" · "}
              {regle.canaux.map(libelleCanal).join(", ")}
            </p>
          </li>
        ))}
      </ul>
      {regles && regles.length === 0 && <p className="mt-3 text-sm text-subtle">Aucune règle.</p>}
      </div>
      </div>
      {confirmation && <ConfirmationDialogue confirmation={confirmation} onFermer={() => setConfirmation(null)} />}
    </div>
  );
}
