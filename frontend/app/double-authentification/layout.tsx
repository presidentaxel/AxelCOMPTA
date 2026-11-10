import { GardeEspaceGestionnaire } from "@/components/GardeEspaceGestionnaire";
import { Marque } from "@/components/Marque";

/** Écran à part : ni barre latérale, ni pages du portefeuille. Il couvre
 * toute la fenêtre tant que le code n'est pas vérifié. */
export default function LayoutDoubleAuthentification({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-canvas-app">
      <GardeEspaceGestionnaire />
      <header className="border-b border-border bg-canvas">
        <div className="mx-auto flex h-14 max-w-md items-center px-4">
          <Marque />
        </div>
      </header>
      <main className="mx-auto w-full max-w-md flex-1 px-4 py-10">{children}</main>
    </div>
  );
}
