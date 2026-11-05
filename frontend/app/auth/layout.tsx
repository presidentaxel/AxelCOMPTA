import { Marque } from "@/components/Marque";

/** Même colonne que l'espace chauffeur : un lien ouvert depuis le téléphone
 * ne doit pas atterrir sur une page nue. Pas de barre du bas, la session
 * n'est pas encore choisie. */
export default function LayoutAuth({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas-app">
      <header className="sticky top-0 z-10 border-b border-border bg-canvas">
        <div className="mx-auto flex h-14 max-w-md items-center px-4">
          <Marque />
        </div>
      </header>
      <main className="mx-auto min-w-0 max-w-md px-4 py-6">{children}</main>
    </div>
  );
}
