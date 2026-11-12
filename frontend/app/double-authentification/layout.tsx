import { GardeEspaceGestionnaire } from "@/components/GardeEspaceGestionnaire";
import { PageAcces } from "@/components/PageAcces";

/** Écran à part : ni barre de navigation, ni pages du portefeuille. Il couvre
 * toute la fenêtre tant que le code n'est pas vérifié. */
export default function LayoutDoubleAuthentification({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-canvas-app">
      <GardeEspaceGestionnaire />
      <PageAcces>{children}</PageAcces>
    </div>
  );
}
