"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  creerRegle,
  ErreurAuthGestionnaire,
  listerDossiers,
  listerMembres,
  listerRegles,
  modifierRegle,
  obtenirSessionGestionnaire,
  supprimerRegle,
  type RegleRappel,
} from "@/lib/auth-gestionnaire";
import type { DossierAgregat } from "@/lib/types";

const CANAUX = [
  { id: "sms", libelle: "SMS" },
  { id: "mail", libelle: "E-mail" },
  { id: "appel", libelle: "Appel" },
];

function libelleCanal(id: string): string {
  return CANAUX.find((canal) => canal.id === id)?.libelle ?? id;
}

const PREFAITS: {
  libelle: string;
  message: string;
  canaux: string[];
  declencheur: string;
  jours_avant: number | null;
}[] = [
  {
    libelle: "15 jours avant la clôture",
    message: "La clôture approche. Relis les pièces de l'exercice.",
    canaux: ["mail"],
    declencheur: "avant_cloture",
    jours_avant: 15,
  },
  {
    libelle: "Compte à ouvrir",
    message: "Ouvre ton compte pour suivre l'exercice.",
    canaux: ["mail", "sms"],
    declencheur: "manuel",
    jours_avant: null,
  },
  {
    libelle: "Pièces à compléter",
    message: "Il reste des pièces à ajouter avant la clôture.",
    canaux: ["sms"],
    declencheur: "manuel",
    jours_avant: null,
  },
];

/** Réglages. Une règle « avant clôture » part seule pour les entreprises
 * concernées. L'envoi réel attend le branchement du canal. */
export default function RappelsPage() {
  const router = useRouter();
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
  const [enCours, setEnCours] = useState(false);
  const [admin, setAdmin] = useState(false);

  useEffect(() => {
    listerRegles()
      .then(async (liste) => {
        const manquantes = PREFAITS.filter(
          (modele) => !liste.some((regle) => regle.libelle === modele.libelle),
        );
        // Seul un admin crée les règles préfaites ; un membre ou une
        // lecture voit la liste telle quelle.
        for (const modele of manquantes) {
          await creerRegle({ ...modele, portee: "tous" }).catch(() => undefined);
        }
        setRegles(manquantes.length > 0 ? await listerRegles() : liste);
      })
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur("Impossible de charger les rappels.");
      });
    listerDossiers()
      .then(setDossiers)
      .catch(() => undefined);
    const session = obtenirSessionGestionnaire();
    listerMembres()
      .then((membres) => {
        const moi = membres.find((membre) => membre.email.toLowerCase() === session?.email.toLowerCase());
        setAdmin(moi ? moi.role === "admin" : true);
      })
      .catch(() => setAdmin(false));
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
    if (regle.declencheur === "avant_cloture" && (!regle.jours_avant || regle.jours_avant < 1)) {
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
    <div className="mx-auto max-w-5xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Rappels</h1>
      <p className="mt-2 text-sm text-subtle">
        Les relances se préparent ici. L&apos;envoi n&apos;est pas branché : aucun SMS, e-mail ou appel ne part.
      </p>

      <div className="mt-8 grid items-start gap-12 lg:grid-cols-3">
      <form
        className="space-y-4 lg:col-span-2"
        onSubmit={(evenement) => {
          evenement.preventDefault();
          void ajouter({
            libelle: libelle.trim(),
            message: message.trim(),
            canaux,
            declencheur,
            jours_avant: declencheur === "avant_cloture" ? Number(jours) : null,
            portee,
            dossier_ids: choisis,
          });
        }}
      >
        <p className="text-sm font-medium text-ink">Votre règle</p>
        {!admin && (
          <p className="text-sm text-subtle">Seule une personne administratrice crée ou modifie une règle.</p>
        )}
        <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Nom" aria-label="Nom de la règle" required disabled={enCours || !admin} />
        <Input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Message" aria-label="Message de la règle" required disabled={enCours || !admin} />
        <div className="flex flex-wrap gap-2">
          {CANAUX.map((canal) => {
            const actif = canaux.includes(canal.id);
            return (
              <button
                key={canal.id}
                type="button"
                aria-pressed={actif}
                disabled={!admin}
                onClick={() =>
                  setCanaux((actuel) => (actif ? actuel.filter((id) => id !== canal.id) : [...actuel, canal.id]))
                }
                className={`rounded-full border px-3 py-1.5 text-sm ${actif ? "border-primary bg-primary-subtle text-primary" : "border-border text-subtle"}`}
              >
                {canal.libelle}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button
            type="button"
            aria-pressed={declencheur === "avant_cloture"}
            disabled={!admin}
            onClick={() => setDeclencheur("avant_cloture")}
            className={`rounded-full border px-3 py-1.5 ${declencheur === "avant_cloture" ? "border-primary bg-primary-subtle text-primary" : "border-border text-subtle"}`}
          >
            Avant la clôture
          </button>
          <button
            type="button"
            aria-pressed={declencheur === "manuel"}
            disabled={!admin}
            onClick={() => setDeclencheur("manuel")}
            className={`rounded-full border px-3 py-1.5 ${declencheur === "manuel" ? "border-primary bg-primary-subtle text-primary" : "border-border text-subtle"}`}
          >
            Bouton sur la fiche
          </button>
          {declencheur === "avant_cloture" && (
            <label className="flex items-center gap-2 text-subtle">
              <Input
                value={jours}
                onChange={(e) => setJours(e.target.value)}
                inputMode="numeric"
                className="w-16"
                aria-label="Jours avant la clôture"
              />
              jours avant
            </label>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            aria-pressed={portee === "tous"}
            disabled={!admin}
            onClick={() => setPortee("tous")}
            className={`rounded-full border px-3 py-1.5 text-sm ${portee === "tous" ? "border-primary bg-primary-subtle text-primary" : "border-border text-subtle"}`}
          >
            Toutes les entreprises
          </button>
          <button
            type="button"
            aria-pressed={portee === "selection"}
            disabled={!admin}
            onClick={() => setPortee("selection")}
            className={`rounded-full border px-3 py-1.5 text-sm ${portee === "selection" ? "border-primary bg-primary-subtle text-primary" : "border-border text-subtle"}`}
          >
            Certaines
          </button>
        </div>
        {portee === "selection" && (
          <ul className="max-h-40 overflow-y-auto rounded-lg border border-border">
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
        <Button type="submit" disabled={enCours || !admin || canaux.length === 0}>
          Enregistrer la règle
        </Button>
      </form>
      <div>
      {erreur && <p className="mb-4 text-sm text-danger">{erreur}</p>}
      <p className="text-sm font-medium text-ink">Règles</p>
      <ul className="mt-3">
        {regles?.map((regle) => (
          <li key={regle.id} className="border-b border-hairline py-4">
            <p className="text-sm font-medium text-ink">{regle.libelle}</p>
            <p className="mt-1 text-sm text-subtle">{regle.message}</p>
            {admin && (
              <div className="mt-2 flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    await modifierRegle(regle.id, { actif: !regle.actif });
                    setRegles(await listerRegles());
                  }}
                >
                  {regle.actif ? "Suspendre" : "Activer"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={async () => {
                    await supprimerRegle(regle.id);
                    setRegles(await listerRegles());
                  }}
                >
                  Supprimer
                </Button>
              </div>
            )}
            <p className="mt-1 text-xs text-subtle">
              {regle.declencheur === "avant_cloture"
                ? `${regle.jours_avant} jours avant la clôture`
                : "Bouton sur la fiche"}
              {" · "}
              {regle.portee === "selection" ? `${regle.dossier_ids.length} entreprise(s)` : "Toutes"}
              {" · "}
              {regle.actif ? "Active" : "Suspendue"}
              {" · Envoi non branché · "}
              {regle.canaux.map(libelleCanal).join(", ")}
            </p>
          </li>
        ))}
      </ul>
      {regles && regles.length === 0 && <p className="mt-3 text-sm text-subtle">Aucune règle.</p>}
      </div>
      </div>
    </div>
  );
}
