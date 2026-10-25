# frontend/

TypeScript / React / Next.js (App Router) — back-office riche + pages de
signature publiques en SSR (doc 03 §2). Design system : voir
[DESIGN.md](../DESIGN.md).

**Dépendances :** le frontend parle à `axelcompta.api.app` (voir
Statuts ci-dessous). Les routes sont encore câblées dans `demo_api`.
Aucun accès direct à la base ou aux modules métier.

## Démarrer en local (démo)

**Changement 2026-09-07** : l'API démo a maintenant besoin d'un Postgres
démarré (persistance réelle des décisions humaines, doc 17 §9 bloc A) —
avant, elle tournait entièrement en mémoire.

```bash
# 0. La base : sur Supabase depuis le 2026-09-24, déjà migrée et amorcée.
#    Détail et variables d'env : backend/README.md, « Lancer l'API de démo ».

# 1. L'API démo (backend/)
set -a && . ../.env && set +a
.venv/bin/uvicorn axelcompta.api.app:app --reload --port 8000

# 2. Le frontend (frontend/)
cd frontend && npm install && npm run dev
```

Puis ouvrir `http://localhost:3000`. `NEXT_PUBLIC_API_BASE_URL` (défaut
`http://localhost:8000`) est configurable via `.env.local` (voir
`.env.example`).

**Pour tester la connexion chauffeur** (`/chauffeur/login`, doc 17 §9
bloc B) : `.env.local` a aussi besoin de `NEXT_PUBLIC_SUPABASE_URL` et
`NEXT_PUBLIC_SUPABASE_ANON_KEY` (mêmes valeurs que `backend/.env`, la clé
anon est faite pour être publique). Sans ça, le dashboard gestionnaire
fonctionne normalement — seule la partie chauffeur en a besoin.

Les trois comptes de démo partagent le mot de passe `DemoChauffeur2026!`
(posé le 2026-09-25, comptes synthétiques) :

| E-mail | Dossier |
|---|---|
| `demo-karim@axelcompta.fr` | Karim |
| `demo-sophie@axelcompta.fr` | Sophie |
| `demo-yanis@axelcompta.fr` | Yanis |

## Les trois écrans clés (V1, doc 11 §3)

Détail complet dans [doc 11](../docs/11-ux-ui.md) — l'UI s'adapte de 1 à 200
dossiers et au statut de chaque dossier (doc 11 §1bis). Le parcours
chauffeur (mobile) est cadré dans [doc 19](../docs/19-parcours-utilisateur.md).

## Statuts

- **Démo (doc 17 §9)** : **une vraie UI**, plus un rapport HTML statique —
  Next.js + Tailwind, tokens `DESIGN.md`, parle à `axelcompta.api.app`
  (`demo_api` câble encore les routes). Fait côté gestionnaire : dashboard, fiche dossier, file de
  revue réelle sur la dépense de Sophie (bloc C), invitation chauffeur
  (bloc B). Interface chauffeur : connexion réelle via Supabase Auth
  (appels REST directs, pas le SDK JS), session en `localStorage`.
  **Depuis le 2026-09-27**, chaque appel à l'API passe par `lib/session.ts` :
  le jeton d'accès (une heure environ) est renouvelé avant son expiration
  avec le jeton de rafraîchissement, et une fois de plus sur un 401. Si ce
  n'est plus possible, la session est effacée et l'utilisateur renvoyé vers
  sa page de connexion (« votre session a expiré »), puis ramené sur la
  page qu'il quittait. Serveur injoignable : message clair, session gardée.
  Routage restructuré en groupe `app/(gestionnaire)/` pour que la
  Sidebar/TopBar ne s'applique qu'aux routes gestionnaire (doc 19 §7 :
  « même socle, deux habillages ») — sans effet sur les URLs.
  **Parcours mobile complet fait (2026-09-09, Semaine 3)** : transactions
  catégorisées, question de catégorisation (`QuestionCategorisation.tsx`,
  démontrée sur Sophie plutôt que Karim — lui n'a par construction aucune
  écriture à trancher, doc 17 §4.1/§9), photo de justificatif
  (`JustificatifPhoto.tsx`, upload réel, pas d'OCR), validation de la liasse
  au téléchargement (case à cocher, sans signature électronique), badge de connexion bancaire selon
  `mode_acces_bancaire`. **Pas fait** : la connexion bancaire directe
  `chauffeur_direct` elle-même (bouton désactivé, stub visuel — toujours
  conditionnée à un canal bancaire réel, Digifactory ou Bridge, doc 16).
  **Clôture/liasse fait (2026-09-11, Semaine 4)** : `ClotureSection.tsx`
  sur la fiche dossier — compte de résultat (CA HT/Charges/Résultat) +
  bilan simplifié (Trésorerie/TVA à payer, absents de l'écran avant ce
  lot) + 5 liens de téléchargement (liasse/CERFA 2065/FEC/grand livre/
  balance, `demo_api.py`) reflétant les décisions humaines appliquées, pas
  le ledger brut.
- **V1 (doc 12, phase 3-4)** : Next.js complet sur `api/` (le vrai backend,
  auth/MFA, multi-tenant), design system (`DESIGN.md`), maquettes Figma
  validées avec 2 utilisateurs cibles (doc 12 §0.3).

## Doc de référence

[doc 11](../docs/11-ux-ui.md) (UX/UI complet),
[doc 19](../docs/19-parcours-utilisateur.md) (parcours gestionnaire/chauffeur),
[DESIGN.md](../DESIGN.md) (design system : tokens, composants, Do's & Don'ts),
[doc 17 §9](../docs/archive/17-plan-demo-journal-2026-09.md#9-semaines-et-jalons).
