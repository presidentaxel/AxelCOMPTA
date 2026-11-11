"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { FormulaireHabilitationExpert } from "@/components/FormulaireHabilitationExpert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  changerRole,
  ErreurAuthGestionnaire,
  integrerMembreSession,
  inviterMembre,
  lireEquipeSession,
  listerMembres,
  obtenirSessionGestionnaire,
  publierEquipeSession,
  reinitialiserMfaMembre,
  retirerMembre,
  type MembrePortefeuille,
  type RoleMembre,
} from "@/lib/auth-gestionnaire";
import { useDroitGestionnaire } from "@/lib/use-droit";

const ROLES: { id: RoleMembre; libelle: string; detail: string }[] = [
  { id: "admin", libelle: "Admin", detail: "Nom, équipe, retraits, règles" },
  { id: "membre", libelle: "Membre", detail: "Invitations et rappels" },
  { id: "lecture", libelle: "Lecture", detail: "Consultation" },
];

export default function EquipePage() {
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const [email, setEmail] = useState("");
  const [membres, setMembres] = useState<MembrePortefeuille[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [emailInvite, setEmailInvite] = useState("");
  const [roleInvite, setRoleInvite] = useState<RoleMembre>("membre");
  const [enCours, setEnCours] = useState(false);
  // Un chargement lancé avant une invitation ou un changement de rôle ne
  // réécrit pas la liste avec la réponse plus ancienne.
  const requeteCourante = useRef(0);

  function retenir(membre: MembrePortefeuille) {
    requeteCourante.current += 1;
    setMembres((actuels) => integrerMembreSession(actuels ?? [], membre));
  }

  useEffect(() => {
    const session = obtenirSessionGestionnaire();
    if (!session) {
      router.replace("/connexion");
      return;
    }
    // Lecture de sessionStorage avant le rafraîchissement réseau.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEmail(session.email);
    const memo = lireEquipeSession();
    if (memo) setMembres(memo);

    let ignore = false;
    const charger = () => {
      const id = ++requeteCourante.current;
      listerMembres()
        .then((liste) => {
          if (ignore || id !== requeteCourante.current) return;
          publierEquipeSession(liste);
          setMembres(liste);
        })
        .catch((exception) => {
          if (ignore || id !== requeteCourante.current) return;
          if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
          else if (!lireEquipeSession()) setErreur("Impossible de charger l'équipe.");
        });
    };
    charger();
    const surVisibilite = () => {
      if (document.visibilityState === "visible") charger();
    };
    document.addEventListener("visibilitychange", surVisibilite);
    return () => {
      ignore = true;
      document.removeEventListener("visibilitychange", surVisibilite);
    };
  }, [router]);

  const liste =
    membres && membres.length > 0
      ? membres
      : email
        ? [{ email, role: "admin" as const, statut: "actif" as const }]
        : [];

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Équipe</h1>
      <p className="mt-2 text-sm text-subtle">Qui voit cette organisation, et jusqu&apos;où.</p>
      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
      {info && (
        <p role="status" className="mt-6 text-sm text-ink">
          {info}
        </p>
      )}

      <div className="mt-8 grid items-start gap-12 lg:grid-cols-3">
      <form
        className="space-y-4 lg:col-span-2"
        onSubmit={async (evenement) => {
          evenement.preventDefault();
          setEnCours(true);
          setErreur(null);
          try {
            const membre = await inviterMembre(emailInvite.trim(), roleInvite);
            setEmailInvite("");
            retenir(membre);
          } catch (exception) {
            setErreur(exception instanceof Error ? exception.message : "Échec de l'invitation.");
          } finally {
            setEnCours(false);
          }
        }}
      >
        <p className="text-sm font-medium text-ink">Inviter quelqu&apos;un</p>
        <Input
          type="email"
          required
          value={emailInvite}
          onChange={(evenement) => setEmailInvite(evenement.target.value)}
          placeholder="E-mail"
          disabled={enCours || !droit.admin}
        />
        <Segment valeur={roleInvite} onChoisir={setRoleInvite} desactive={!droit.admin} />
        <ul className="space-y-1">
          {ROLES.map((role) => (
            <li key={role.id} className="text-sm text-subtle">
              <span className="font-medium text-ink">{role.libelle}.</span> {role.detail}
            </li>
          ))}
        </ul>
        <Button type="submit" disabled={enCours || !droit.admin} className="w-full">
          Envoyer l&apos;invitation
        </Button>
      </form>
      <ul>
        {liste.map((membre) => (
          <li key={membre.email} className="border-b border-hairline py-4">
            <p className="text-sm font-medium text-ink">
              {membre.email}
              <span className="font-normal text-subtle">
                {" · "}
                {membre.statut === "actif" ? "Invitation acceptée" : "Invitation envoyée"}
                {membre.email === email ? " · vous" : ""}
              </span>
            </p>
            <div className="mt-3">
              <Segment
                valeur={membre.role}
                desactive={!droit.admin}
                onChoisir={async (role) => {
                  if (role === membre.role || !droit.admin) return;
                  const soi = membre.email === email;
                  const phrase = soi
                    ? `Changer votre propre rôle en ${role} ?`
                    : `Donner le rôle ${role} à ${membre.email} ?`;
                  if (!window.confirm(phrase)) return;
                  try {
                    const misAJour = await changerRole(membre.email, role);
                    retenir(misAJour);
                  } catch (exception) {
                    setErreur(exception instanceof Error ? exception.message : "Échec du changement.");
                  }
                }}
              />
            </div>
            {droit.admin && membre.email !== email && (
              <div className="mt-2 flex gap-2">
                {membre.statut !== "actif" && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      try {
                        const renvoye = await inviterMembre(membre.email, membre.role);
                        retenir(renvoye);
                      } catch (exception) {
                        setErreur(exception instanceof Error ? exception.message : "Échec du renvoi.");
                      }
                    }}
                  >
                    Renvoyer
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-danger"
                  onClick={async () => {
                    if (!window.confirm(`Retirer l'accès de ${membre.email} ?`)) return;
                    try {
                      await retirerMembre(membre.email);
                      requeteCourante.current += 1;
                      setMembres((actuel) => actuel?.filter((ligne) => ligne.email !== membre.email) ?? null);
                    } catch (exception) {
                      setErreur(exception instanceof Error ? exception.message : "Échec du retrait.");
                    }
                  }}
                >
                  Retirer l&apos;accès
                </Button>
                {membre.statut === "actif" && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      const phrase =
                        `Réinitialiser la double authentification de ${membre.email} ? ` +
                        "Il enrôlera un nouveau téléphone à sa prochaine connexion.";
                      if (!window.confirm(phrase)) return;
                      try {
                        await reinitialiserMfaMembre(membre.email);
                        setInfo(`Double authentification de ${membre.email} réinitialisée.`);
                      } catch (exception) {
                        setErreur(exception instanceof Error ? exception.message : "Échec.");
                      }
                    }}
                  >
                    Réinitialiser la double authentification
                  </Button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      </div>
      {droit.admin && <FormulaireHabilitationExpert actif={droit.admin} />}
    </div>
  );
}

function Segment({
  valeur,
  onChoisir,
  desactive = false,
}: {
  valeur: RoleMembre;
  onChoisir: (role: RoleMembre) => void;
  desactive?: boolean;
}) {
  return (
    <div className="flex w-full overflow-hidden rounded-md border border-border">
      {ROLES.map((role) => (
        <button
          key={role.id}
          type="button"
          title={role.detail}
          aria-pressed={valeur === role.id}
          disabled={desactive}
          onClick={() => onChoisir(role.id)}
          className={`h-9 flex-1 border-l border-border text-sm first:border-l-0 disabled:opacity-50 ${
            valeur === role.id ? "bg-surface-soft font-medium text-ink" : "text-subtle hover:bg-canvas-app"
          }`}
        >
          {role.libelle}
        </button>
      ))}
    </div>
  );
}
