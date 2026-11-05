"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  accepterInvitation,
  definirMotDePasse,
  ErreurAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { lireFragmentAuth, pageInvitation } from "@/lib/auth-lien";

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
      const recu = lireFragmentAuth(fragment);
      if (pageInvitation(recu.accessToken) === "gestionnaire") {
        window.location.replace(`/auth/lien${fragment}`);
        return;
      }
    } catch (exception) {
      setErreur(exception instanceof ErreurAuthChauffeur ? exception.message : "Lien invalide.");
      setEtape("erreur");
      return;
    }
    accepterInvitation(fragment)
      .then((session) => {
        setDossierId(session.dossierId);
        setEtape("definir_mot_de_passe");
      })
      .catch((exception) => {
        setErreur(
          exception instanceof ErreurAuthChauffeur ? exception.message : "Lien invalide.",
        );
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
      router.push(`/chauffeur/${dossierId}`);
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur
          ? exception.message
          : "Échec de l'enregistrement du mot de passe.",
      );
    } finally {
      setEnCours(false);
    }
  }

  if (etape === "verification") {
    return <p className="text-sm text-subtle">Vérification de votre invitation…</p>;
  }

  if (etape === "erreur") {
    return (
      <div>
        <p className="text-sm text-danger">{erreur}</p>
        <p className="mt-2 text-sm text-subtle">
          Redemandez une invitation à votre gestionnaire, ou{" "}
          <Link href="/chauffeur/login" className="inline-flex min-h-11 items-center text-primary hover:underline">
            connectez-vous
          </Link>{" "}
          si vous avez déjà un mot de passe.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-xl font-bold text-ink">Bienvenue</h1>
      <p className="mb-6 text-sm text-subtle">
        Choisissez un mot de passe pour vos prochaines connexions.
      </p>
      <form className="space-y-3" onSubmit={valider}>
        <Input
          type="password"
          uiSize="lg"
          value={motDePasse}
          onChange={(evenement) => setMotDePasse(evenement.target.value)}
          placeholder="Nouveau mot de passe"
          required
          minLength={8}
          disabled={enCours}
        />
        {erreur && <p className="text-sm text-danger">{erreur}</p>}
        <Button type="submit" disabled={enCours} className="w-full">
          {enCours ? "Enregistrement…" : "Valider"}
        </Button>
      </form>
    </div>
  );
}
