"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { demanderReinitialisation, envoyerLienMagique } from "@/lib/auth-chauffeur";
import { messageVisible } from "@/lib/messages";
import { sessionAExpire } from "@/lib/session";

type Mode = "mot_de_passe" | "lien" | "oubli";

/** Connexion par mot de passe, lien magique, ou e-mail de réinitialisation.
 * Les deux derniers atterrissent sur `/auth/lien`. */
export function FormulaireConnexion(props: {
  titre: string;
  sousTitre: string;
  onConnecte: (email: string, motDePasse: string) => Promise<void>;
}) {
  return (
    <Suspense fallback={<p className="text-sm text-subtle">Chargement…</p>}>
      <Formulaire {...props} />
    </Suspense>
  );
}

function Formulaire({
  titre,
  sousTitre,
  onConnecte,
}: {
  titre: string;
  sousTitre: string;
  onConnecte: (email: string, motDePasse: string) => Promise<void>;
}) {
  const recherche = useSearchParams();
  const modeInitial = recherche.get("mode");
  const [mode, setMode] = useState<Mode>(
    modeInitial === "lien" || modeInitial === "oubli" ? modeInitial : "mot_de_passe",
  );
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    // Arrivée depuis une page interne dont la session n'a pas pu être
    // renouvelée (`lib/session.ts`) : on dit pourquoi on est là.
    if (sessionAExpire(window.location.search)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setInfo("Votre session a expiré. Reconnectez-vous pour reprendre où vous en étiez.");
    }
  }, []);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnCours(true);
    setErreur(null);
    setInfo(null);
    try {
      const adresse = email.trim();
      if (mode === "lien") {
        await envoyerLienMagique(adresse);
        setInfo("Si un compte existe pour cette adresse, le lien de connexion est envoyé.");
      } else if (mode === "oubli") {
        await demanderReinitialisation(adresse);
        setInfo("Si un compte existe pour cette adresse, le lien de réinitialisation est envoyé.");
      } else {
        await onConnecte(adresse, motDePasse);
      }
    } catch (exception) {
      setErreur(messageVisible(exception, "Échec de la connexion."));
    } finally {
      setEnCours(false);
    }
  }

  function basculer(suivant: Mode) {
    setMode(suivant);
    setErreur(null);
    setInfo(null);
  }

  return (
    <div>
      <h1 className="mb-1 text-xl font-bold text-ink">{titre}</h1>
      <p className="mb-6 text-sm text-subtle">{sousTitre}</p>
      <form className="space-y-3" onSubmit={soumettre}>
        <label className="block text-sm text-subtle" htmlFor="connexion-email">
          E-mail
        </label>
        <Input
          id="connexion-email"
          type="email"
          uiSize="lg"
          autoComplete="email"
          value={email}
          onChange={(evenement) => setEmail(evenement.target.value)}
          placeholder="vous@exemple.fr"
          required
          disabled={enCours}
        />
        {mode === "mot_de_passe" && (
          <>
            <label className="block text-sm text-subtle" htmlFor="connexion-mot-de-passe">
              Mot de passe
            </label>
            <Input
              id="connexion-mot-de-passe"
              type="password"
              uiSize="lg"
              autoComplete="current-password"
              value={motDePasse}
              onChange={(evenement) => setMotDePasse(evenement.target.value)}
              required
              disabled={enCours}
            />
          </>
        )}
        {erreur && (
          <p role="alert" className="text-sm text-danger">
            {erreur}
          </p>
        )}
        {info && <p className="text-sm text-subtle">{info}</p>}
        <Button type="submit" disabled={enCours} className="w-full">
          {enCours
            ? "Envoi…"
            : mode === "lien"
              ? "Recevoir le lien"
              : mode === "oubli"
                ? "Recevoir le lien de réinitialisation"
                : "Se connecter"}
        </Button>
      </form>
      <div className="mt-4 flex flex-col gap-2 text-sm">
        {mode !== "lien" && (
          <button type="button" className="min-h-11 text-left text-primary hover:underline" onClick={() => basculer("lien")}>
            Recevoir un lien de connexion
          </button>
        )}
        {mode !== "oubli" && (
          <button type="button" className="min-h-11 text-left text-primary hover:underline" onClick={() => basculer("oubli")}>
            Mot de passe oublié
          </button>
        )}
        {mode !== "mot_de_passe" && (
          <button
            type="button"
            className="min-h-11 text-left text-primary hover:underline"
            onClick={() => basculer("mot_de_passe")}
          >
            Se connecter avec un mot de passe
          </button>
        )}
      </div>
    </div>
  );
}
