import { LienAction } from "@/components/LienAction";

/** Suite proposée quand un lien d'authentification ne peut plus servir. */
export function SuitesAuth({ invitation = false }: { invitation?: boolean }) {
  return (
    <div className="mt-6 flex flex-col items-start">
      <LienAction href="/chauffeur/login?mode=lien">Recevoir un nouveau lien</LienAction>
      <LienAction href="/chauffeur/login?mode=oubli">Mot de passe oublié</LienAction>
      <LienAction href="/chauffeur/login">Se connecter</LienAction>
      {invitation ? (
        <p className="mt-2 text-sm text-subtle">
          Si vous n&apos;avez pas encore de mot de passe, demandez à votre gestionnaire de renvoyer
          l&apos;invitation.
        </p>
      ) : (
        <LienAction href="/connexion">Connexion gestionnaire</LienAction>
      )}
    </div>
  );
}
