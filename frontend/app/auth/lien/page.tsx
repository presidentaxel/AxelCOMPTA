"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

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
import { MOT_DE_PASSE_MIN, motDePasseAcceptable } from "@/lib/messages-auth";
import { messageVisible } from "@/lib/messages";

type Etape = "lecture" | "mot_de_passe" | "email_confirme" | "erreur";

/** Cible des liens Supabase : magique, réinitialisation, confirmation
 * d'adresse. Les jetons restent dans le fragment, jamais envoyés au serveur. */
export default function LienAuthPage() {
  const router = useRouter();
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
      const code = new URLSearchParams(window.location.search).get("code");
      if (code && !window.location.hash.includes("access_token=")) {
        throw new ErreurAuthChauffeur(
          "Ce lien ne peut pas être terminé ici. Redemandez un lien de connexion ou de réinitialisation.",
        );
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
      setErreur(messageVisible(exception, "Lien invalide."));
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
      const refus = motDePasseAcceptable(motDePasse);
      if (refus) {
        setErreur(refus);
        return;
      }
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
      setErreur(
        exception instanceof Error
          ? exception.message
          : "Échec de l'enregistrement du mot de passe.",
      );
    } finally {
      setEnCours(false);
    }
  }

  if (etape === "lecture") {
    return <p className="mx-auto mt-24 max-w-sm px-4 text-sm text-subtle">Vérification du lien…</p>;
  }

  if (etape === "erreur") {
    return (
      <main className="mx-auto mt-24 max-w-sm px-4">
        <p role="alert" className="text-sm text-danger">
          {erreur ?? "Ce lien est invalide ou expiré."}
        </p>
        <p className="mt-2 flex flex-col gap-2 text-sm text-subtle">
          <Link href="/chauffeur/login?mode=lien" className="min-h-11 text-primary hover:underline">
            Recevoir un nouveau lien
          </Link>
          <Link href="/chauffeur/login?mode=oubli" className="min-h-11 text-primary hover:underline">
            Mot de passe oublié
          </Link>
          <Link href="/chauffeur/login" className="min-h-11 text-primary hover:underline">
            Connexion chauffeur
          </Link>
          <Link href="/connexion" className="min-h-11 text-primary hover:underline">
            Connexion gestionnaire
          </Link>
        </p>
      </main>
    );
  }

  if (etape === "email_confirme") {
    return (
      <main className="mx-auto mt-24 max-w-sm px-4">
        <h1 className="mb-2 text-xl font-bold text-ink">Adresse confirmée</h1>
        <p className="mb-4 text-sm text-subtle">La nouvelle adresse est active.</p>
        <Button type="button" onClick={() => router.replace(destination)}>
          Continuer
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto mt-24 max-w-sm px-4">
      <h1 className="mb-1 text-xl font-bold text-ink">
        {premiereConnexion ? "Bienvenue" : "Nouveau mot de passe"}
      </h1>
      <p className="mb-6 text-sm text-subtle">
        Choisissez un mot de passe d&apos;au moins {MOT_DE_PASSE_MIN} caractères pour vos
        prochaines connexions.
      </p>
      <form className="space-y-3" onSubmit={valider}>
        <label className="block text-sm text-subtle" htmlFor="lien-mot-de-passe">
          Nouveau mot de passe
        </label>
        <Input
          id="lien-mot-de-passe"
          type="password"
          uiSize="lg"
          autoComplete="new-password"
          value={motDePasse}
          onChange={(evenement) => setMotDePasse(evenement.target.value)}
          required
          minLength={MOT_DE_PASSE_MIN}
          disabled={enCours}
        />
        {erreur && (
          <p role="alert" className="text-sm text-danger">
            {erreur}
          </p>
        )}
        <Button type="submit" disabled={enCours} className="w-full">
          {enCours ? "Enregistrement…" : "Valider"}
        </Button>
      </form>
    </main>
  );
}
