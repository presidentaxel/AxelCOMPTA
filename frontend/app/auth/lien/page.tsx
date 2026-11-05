"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { SuitesAuth } from "@/components/SuitesAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  connexionParMotDePasse,
  decoderChargeUtileJwt,
  definirMotDePasseAvecJeton,
  ErreurAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { connexionGestionnaire } from "@/lib/auth-gestionnaire";
import {
  lireFragmentAuth,
  ouvrirSessionDepuisJetons,
  pageInvitation,
  type FragmentAuth,
} from "@/lib/auth-lien";
import {
  INDICATION_MOT_DE_PASSE,
  LONGUEUR_MIN_MOT_DE_PASSE,
  MESSAGE_LIEN_INCOMPLET,
  messageParametresAuth,
  traduireExceptionAuth,
} from "@/lib/messages-auth";

type Etape = "lecture" | "mot_de_passe" | "email_confirme" | "erreur";

/** Cible des liens Supabase : magique, réinitialisation, confirmation
 * d'adresse. Les jetons restent dans le fragment, jamais envoyés au serveur. */
export default function LienAuthPage() {
  const router = useRouter();
  const idMotDePasse = useId();
  const [etape, setEtape] = useState<Etape>("lecture");
  const [fragment, setFragment] = useState<FragmentAuth | null>(null);
  const [destination, setDestination] = useState("/");
  const [motDePasse, setMotDePasse] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [premiereConnexion, setPremiereConnexion] = useState(false);

  useEffect(() => {
    // Le fragment `#access_token` n'existe que dans le navigateur.
    /* eslint-disable react-hooks/set-state-in-effect */
    try {
      const recherche = new URLSearchParams(window.location.search);
      const messageRecherche = messageParametresAuth(recherche);
      if (messageRecherche) throw new ErreurAuthChauffeur(messageRecherche);
      const code = recherche.get("code");
      if (code && !window.location.hash.includes("access_token=")) {
        throw new ErreurAuthChauffeur(MESSAGE_LIEN_INCOMPLET);
      }
      const recu = lireFragmentAuth(window.location.hash);
      if (recu.type === "invite" && pageInvitation(recu.accessToken) === "chauffeur") {
        window.location.replace(`/chauffeur/accepter-invitation${window.location.hash}`);
        return;
      }
      if (recu.type === "invite") {
        setFragment(recu);
        setPremiereConnexion(true);
        setEtape("mot_de_passe");
        return;
      }
      if (recu.type === "recovery") {
        setFragment(recu);
        setEtape("mot_de_passe");
        return;
      }
      const chemin = ouvrirSessionDepuisJetons(recu.accessToken, recu.refreshToken);
      if (recu.type === "email_change") {
        setDestination(chemin);
        setEtape("email_confirme");
        return;
      }
      router.replace(chemin);
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
      setEtape("erreur");
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [router]);

  async function valider(evenement: React.FormEvent) {
    evenement.preventDefault();
    if (!fragment) return;
    setEnCours(true);
    setErreur(null);
    try {
      await definirMotDePasseAvecJeton(fragment.accessToken, motDePasse);
      const charge = decoderChargeUtileJwt(fragment.accessToken);
      const email = typeof charge.email === "string" ? charge.email : "";
      const meta = (charge.app_metadata ?? {}) as { dossier_id?: string };
      if (meta.dossier_id) {
        const session = await connexionParMotDePasse(email, motDePasse);
        router.replace(`/chauffeur/${session.dossierId}`);
      } else {
        await connexionGestionnaire(email, motDePasse);
        router.replace("/");
      }
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
    } finally {
      setEnCours(false);
    }
  }

  if (etape === "lecture") {
    return <p className="text-sm text-subtle">Vérification du lien…</p>;
  }

  if (etape === "erreur") {
    return (
      <div>
        <h1 className="mb-2 text-xl font-bold text-ink">Lien inutilisable</h1>
        <p role="alert" className="text-sm text-danger">
          {erreur}
        </p>
        <SuitesAuth />
      </div>
    );
  }

  if (etape === "email_confirme") {
    return (
      <div>
        <h1 className="mb-2 text-xl font-bold text-ink">Adresse confirmée</h1>
        <p className="mb-4 text-sm text-subtle">La nouvelle adresse est active.</p>
        <Button type="button" onClick={() => router.replace(destination)}>
          Continuer
        </Button>
      </div>
    );
  }

  const idRegle = `${idMotDePasse}-regle`;
  return (
    <div>
      <h1 className="mb-1 text-xl font-bold text-ink">
        {premiereConnexion ? "Bienvenue" : "Nouveau mot de passe"}
      </h1>
      <p className="mb-6 text-sm text-subtle">
        Choisissez un mot de passe pour vos prochaines connexions.
      </p>
      <form className="space-y-3" onSubmit={valider}>
        <div className="space-y-1">
          <label htmlFor={idMotDePasse} className="block text-sm font-medium text-ink">
            Nouveau mot de passe
          </label>
          <p id={idRegle} className="text-sm text-subtle">
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
          <p role="alert" className="text-sm text-danger">
            {erreur}
          </p>
        )}
        <Button type="submit" disabled={enCours} className="w-full">
          {enCours ? "Enregistrement…" : "Valider"}
        </Button>
      </form>
    </div>
  );
}
