import Link from "next/link";

const LIEN = "text-left text-sm text-primary hover:underline";

/** Suite proposée quand un lien d'authentification ne peut plus servir. */
export function SuitesAuth({ invitation = false }: { invitation?: boolean }) {
  return (
    <div className="mt-4 flex flex-col items-start gap-2">
      <Link href="/chauffeur/login?mode=lien" className={LIEN}>
        Recevoir un nouveau lien
      </Link>
      <Link href="/chauffeur/login?mode=oubli" className={LIEN}>
        Mot de passe oublié
      </Link>
      <Link href="/chauffeur/login" className={LIEN}>
        Se connecter
      </Link>
      {invitation ? (
        <p className="text-sm text-subtle">
          Si vous n&apos;avez pas encore de mot de passe, demandez à votre gestionnaire de renvoyer
          l&apos;invitation.
        </p>
      ) : (
        <Link href="/connexion" className={LIEN}>
          Connexion gestionnaire
        </Link>
      )}
    </div>
  );
}
