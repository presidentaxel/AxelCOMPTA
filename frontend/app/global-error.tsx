"use client";

/** Next.js 16 : filet de secours pour une erreur non interceptée dans le
 * layout racine lui-même (jamais vu jusqu'ici en usage normal — la vraie
 * gestion d'erreur applicative reste dans chaque écran). Nécessaire depuis
 * la migration Next 16 (avant : absent, jamais réclamé par Next 14). */
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="fr">
      <body className="flex min-h-dvh items-center justify-center bg-canvas-app text-ink">
        <div className="text-center">
          <p className="mb-3 text-sm text-subtle">Une erreur inattendue est survenue.</p>
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-md border border-border-strong bg-canvas px-4 py-2 text-sm font-semibold hover:bg-canvas-app"
          >
            Réessayer
          </button>
        </div>
      </body>
    </html>
  );
}
