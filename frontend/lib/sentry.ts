/** Envoie les erreurs du navigateur à Sentry quand le DSN est posé.
 * Sans DSN, ne fait rien : la démo locale n'a pas de projet Sentry. */

type Cible = { cle: string; magasin: string };

export function cibleSentry(dsn: string): Cible | null {
  const morceaux = dsn.match(/^https:\/\/([^@]+)@([^/]+)\/(\d+)$/);
  if (!morceaux) return null;
  const [, cle, hote, projet] = morceaux;
  return { cle, magasin: `https://${hote}/api/${projet}/store/` };
}

export function installerSentry(dsn = process.env.NEXT_PUBLIC_SENTRY_DSN): void {
  if (typeof window === "undefined") return;
  const cible = dsn ? cibleSentry(dsn) : null;
  if (!cible) return;
  window.addEventListener("error", (evenement) => {
    const corps = JSON.stringify({ message: evenement.message, level: "error" });
    void fetch(cible.magasin, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Sentry-Auth": `Sentry sentry_version=7, sentry_key=${cible.cle}, sentry_client=axelcompta/0.0.1`,
      },
      body: corps,
      keepalive: true,
    });
  });
}
