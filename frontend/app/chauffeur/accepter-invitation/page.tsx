"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { EntreeChauffeur } from "@/components/EntreeChauffeur";
import { SuitesAuth } from "@/components/SuitesAuth";
import { TitreEcran } from "@/components/TitreEcran";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  accepterInvitation,
  definirMotDePasse,
  ErreurAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { lireFragmentAuth, pageInvitation } from "@/lib/auth-lien";
import {
  INDICATION_MOT_DE_PASSE,
  LONGUEUR_MIN_MOT_DE_PASSE,
  messageParametresAuth,
  traduireExceptionAuth,
} from "@/lib/messages-auth";

type Etape = "verification" | "definir_mot_de_passe" | "erreur";

/** Page cible du lien envoyé par `POST /dossiers/{id}/inviter` (doc 17 §9
 * bloc B) — Supabase redirige ici avec les jetons dans le fragment d'URL
 * (`#access_token=...`), jamais dans l'URL visible ni envoyé au serveur.
 *
 * **Infra requise côté Louis, pas du code** : ajouter
 * `.../chauffeur/accepter-invitation` aux "Redirect URLs" autorisées dans
 * le dashboard Supabase (Authentication → URL Configuration) — sinon
 * Supabase redirige vers sa propre page par défaut.
 */
export default function AccepterInvitationPage() {
  const router = useRouter();
  const idMotDePasse = useId();
  const [etape, setEtape] = useState<Etape>("verification");
  const [erreur, setErreur] = useState<string | null>(null);
  const [motDePasse, setMotDePasse] = useState("");
  const [dossierId, setDossierId] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    // Le fragment `#access_token` n'existe que dans le navigateur.
    /* eslint-disable react-hooks/set-state-in-effect */
    const fragment = window.location.hash;
    try {
      const messageRecherche = messageParametresAuth(new URLSearchParams(window.location.search));
      if (messageRecherche) throw new ErreurAuthChauffeur(messageRecherche);
      const recu = lireFragmentAuth(fragment);
      if (pageInvitation(recu.accessToken) === "gestionnaire") {
        window.location.replace(`/auth/lien${fragment}`);
        return;
      }
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
      setEtape("erreur");
      return;
    }
    accepterInvitation(fragment)
      .then((session) => {
        setDossierId(session.dossierId);
        setEtape("definir_mot_de_passe");
      })
      .catch((exception) => {
        setErreur(traduireExceptionAuth(exception));
        setEtape("erreur");
      });
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  async function valider(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      await definirMotDePasse(motDePasse);
      router.replace(`/chauffeur/${dossierId}`);
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
    } finally {
      setEnCours(false);
    }
  }

  if (etape === "verification") {
    return (
      <p role="status" className="pt-4 text-base text-subtle">
        Vérification de votre invitation…
      </p>
    );
  }

  if (etape === "erreur") {
    return (
      <div className="pt-4">
        <TitreEcran titre="Invitation inutilisable" />
        <p role="alert" className="text-base text-danger">
          {erreur}
        </p>
        <EntreeChauffeur>
          <SuitesAuth invitation />
        </EntreeChauffeur>
      </div>
    );
  }

  const idRegle = `${idMotDePasse}-regle`;
  return (
    <div className="pt-4">
      <TitreEcran titre="Bienvenue">
        Choisissez un mot de passe pour vos prochaines connexions.
      </TitreEcran>
      <form className="space-y-4" onSubmit={valider}>
        <div className="space-y-2">
          <label htmlFor={idMotDePasse} className="block text-base font-semibold text-ink">
            Nouveau mot de passe
          </label>
          <p id={idRegle} className="text-base text-subtle">
            {INDICATION_MOT_DE_PASSE}
          </p>
          <Input
            id={idMotDePasse}
            name="new-password"
            type="password"
            autoComplete="new-password"
            uiSize="lg"
            value={motDePasse}
            onChange={(evenement) => setMotDePasse(evenement.target.value)}
            required
            minLength={LONGUEUR_MIN_MOT_DE_PASSE}
            disabled={enCours}
            aria-describedby={idRegle}
            aria-invalid={erreur ? true : undefined}
          />
        </div>
        {erreur && (
          <p role="alert" className="text-base text-danger">
            {erreur}
          </p>
        )}
        <Button type="submit" size="lg" disabled={enCours} className="h-12 w-full text-base">
          {enCours ? "Enregistrement…" : "Valider"}
        </Button>
      </form>
    </div>
  );
}
