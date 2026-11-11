import Link from "next/link";

/** AXE-859 : les textes juridiques, accessibles depuis les deux espaces et
 * depuis la connexion. */
export function LiensJuridiques({ className = "" }: { className?: string }) {
  return (
    <nav aria-label="Informations légales" className={`text-xs text-subtle ${className}`}>
      <ul className="flex flex-wrap gap-x-3">
        <li>
          <Link href="/legal/mentions-legales" className="inline-flex min-h-11 items-center">
            Mentions légales
          </Link>
        </li>
        <li>
          <Link href="/legal/confidentialite" className="inline-flex min-h-11 items-center">
            Confidentialité
          </Link>
        </li>
      </ul>
    </nav>
  );
}
