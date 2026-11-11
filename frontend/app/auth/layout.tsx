import { PageAcces } from "@/components/PageAcces";

/** Un lien ouvert depuis le téléphone ne doit pas atterrir sur une page nue :
 * même cadre que la connexion. Pas de navigation, la session n'est pas encore
 * choisie. */
export default function LayoutAuth({ children }: { children: React.ReactNode }) {
  return <PageAcces>{children}</PageAcces>;
}
