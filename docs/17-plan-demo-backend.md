# 17 — Mode réel

> Dernière mise à jour : 2026-11-10. Remplace le plan de démo, archivé tel
> quel dans [archive/17-plan-demo-2026-11.md](archive/17-plan-demo-2026-11.md)
> (et, pour septembre, [archive/17-plan-demo-journal-2026-09.md](archive/17-plan-demo-journal-2026-09.md)).
> L'état du projet est dans le [doc 12](12-roadmap-todo.md).

## 1. Ce qui a changé le 2026-11-05

Serenity a annoncé que ses premiers chauffeurs sont sur Digifactory (13
contacts, dont 7 nouveaux). Décision de Louis : la plateforme passe en
**mode réel**.

- **La base Supabase `AxelCompta` (eu-west-1) est la base de production**
  du portefeuille Serenity. Son identifiant interne reste `TENANT_DEMO`
  (historique, jamais affiché) ; son nom affiché est « Serenity ».
- **Le menu Démo est retiré** (code et routes `/demo/*`). Il remettait la
  démo à neuf par la connexion propriétaire en levant les verrous
  d'immuabilité : ce chemin n'existe plus.
- **Digifactory est le canal bancaire réel**. Le réglage qui le
  « débranchait » pour la démo est retiré.
- **Aucun compte n'est créé à l'import** des contacts Digifactory
  (`scripts/ajouter_chauffeurs_digifactory.py`). Le dirigeant est invité
  par Serenity avec sa vraie adresse (écran Invitations), puis confirme sa
  configuration (AXE-730).

## 2. Données retirées de la base

Faites sur décision de Louis du 2026-11-05 :

| Quoi | Sort |
|---|---|
| Dossiers `DEMO_karim`, `DEMO_yanis`, puis `DEMO_sophie` | Supprimés définitivement, avec leurs écritures, décisions, preuves, justificatifs et lignes du journal d'audit, et leurs comptes `demo-*@axelcompta.fr` |
| Compte gestionnaire `demo@axelcompta.fr` | Supprimé. Serenity est invité avec sa vraie adresse depuis l'écran Équipe |
| Comptes `demo-digi-*@axelcompta.fr` (6) | Supprimés. Les dossiers `DIGI_*` et leurs opérations restent |

**Il n'y a plus aucun dossier ni compte de démo en base.** Comptes restants :
Louis et Arthur, admins du portefeuille.

## 3. Tests et reviews UX

Karim, Sophie et Yanis ne vivent plus que dans les **tests** (jeux en
mémoire, et base locale des tests d'intégration via `amorcer_demo`).
`python -m axelcompta.demo_seed` et `scripts/creer_comptes_demo_chauffeurs.py`
n'existent plus : rien ne peut recréer un dossier fictif en base.

Pour voir l'espace chauffeur sur de vraies données pendant la période de
test : un compte réservé à Louis qui choisit le dossier (AXE-822).

## 4. Importer les vrais chauffeurs

Depuis `backend/` (`.env` à la racine) :

```bash
.venv/bin/python scripts/ajouter_chauffeurs_digifactory.py --lister            # contacts, rien n'est écrit
.venv/bin/python scripts/ajouter_chauffeurs_digifactory.py --contacts 7416,8780 --sans-synchro
.venv/bin/python scripts/ajouter_chauffeurs_digifactory.py --contacts 7416,8780  # puis synchro
```

Le compte Digifactory de Serenity contient aussi des contacts qui ne sont
pas des chauffeurs (ses sociétés, des plateformes) : seuls les contacts
listés deviennent des dossiers (AXE-726). Au 2026-11-05, 7 contacts ne sont
pas encore en base : 7416, 8780, 9692, 20550, 21430, 22755 et 86930.

Un dossier `DIGI_<nr>` par contact, posé en SASU à l'IS sur l'année civile,
forme reprise de Sirene quand le contact a un SIREN. Le reste de la
configuration est à confirmer par le dirigeant (AXE-730). La suite du
chemin vers un premier mois exporté : AXE-727 à AXE-733.

## 5. Lancer l'application

Commandes : [backend/README.md](../backend/README.md), section « Lancer
l'API de démo ». Après un `git pull`, `alembic upgrade head` avant l'API.
Le CORS n'accepte que `http://localhost:3000` ; `DATABASE_URL_WEB` doit
être défini, sinon chaque requête répond 500.

### Compte de test (AXE-822)

Pour voir l'espace chauffeur d'un vrai dossier avant que les chauffeurs aient
un compte : un compte de test, pour Louis seulement, daté.

    python scripts/compte_de_test.py creer test@exemple.fr --jusqu-au 2026-12-31
    python scripts/compte_de_test.py supprimer test@exemple.fr

Connecté sur `/chauffeur/login`, il choisit le dossier (« Quel dossier ? »)
et voit l'espace du chauffeur, avec un bandeau « Mode test, lecture seule ».
Toute écriture répond 403. Il ne lit que les dossiers de son portefeuille
(`X-Dossier`, vérifié par l'API), n'a aucune route gestionnaire, et chaque
dossier ouvert est tracé au journal d'audit (`consultation_compte_test`).
Passé la date de fin (90 jours au plus), l'API le refuse. À supprimer avant
que les chauffeurs se connectent.

## 6. Risques

| Risque | Parade |
|---|---|
| Les données de vrais chauffeurs vivent dans la même base que le développement | Plus de chemin applicatif qui lève les verrous ; migrations appliquées seulement après revue. Sauvegardes et restauration testée : AXE-811. Isolation stricte de la production : AXE-810 |
| Des sociétés du compte Digifactory ne sont pas des chauffeurs (Serenity Groupe, Serenity Investissement, Bolt) | Import sur liste explicite (§4) ; tags d'entreprises pour les exclure des traitements (AXE-829, fait le 06/11) |
| Le mode expert n'a pas encore sa garde juridique | Ne pas l'ouvrir à Serenity avant AXE-800 (doc 02 §2.3) |
