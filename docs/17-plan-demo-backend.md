# 17 — Mode réel et dossier de review UX

> Dernière mise à jour : 2026-11-05. Remplace le plan de démo, archivé tel
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
| Dossiers `DEMO_karim` et `DEMO_yanis` | Supprimés définitivement, avec leurs écritures, décisions, preuves et lignes du journal d'audit, et leurs comptes `demo-karim@` et `demo-yanis@` |
| Compte gestionnaire `demo@axelcompta.fr` | Supprimé. Serenity est invité avec sa vraie adresse depuis l'écran Équipe |
| Comptes `demo-digi-*@axelcompta.fr` (6) | Supprimés. Les dossiers `DIGI_*` et leurs opérations restent |
| `DEMO_sophie` et `demo-sophie@axelcompta.fr` | **Gardés** : dossier de review UX (§3) |

Admins du portefeuille : Louis et Arthur.

## 3. Le dossier de review UX : Sophie

Un seul dossier fictif reste en base, pour tester l'interface sans toucher
aux données d'un vrai chauffeur.

- Compte : `demo-sophie@axelcompta.fr`, mot de passe dans
  [frontend/README.md](../frontend/README.md).
- Profil : EURL à l'IS, TVA, Uber et Bolt, une dépense ambiguë (Zara) à
  trancher, exercice 2025 avec une frise avancée jusqu'au greffe.
- Il apparaît dans la liste Entreprises de Serenity. Ne pas l'inviter, ne
  pas le compter dans les chiffres du pilote.
- Il n'y a plus de remise à neuf. Une décision se corrige ou s'annule
  depuis l'écran (Mouvements, « Annuler »). Si le dossier doit repartir de
  zéro, c'est une opération manuelle sur la base, à décider au cas par cas.
- Recréer le dossier sur une base vide : `python -m axelcompta.demo_seed`
  (il ne pose plus que Sophie), puis
  `python scripts/creer_comptes_demo_chauffeurs.py`.

Karim et Yanis restent dans les **tests** (jeux en mémoire et tests
d'intégration sur une base locale), jamais dans la base Supabase.

## 4. Importer les vrais chauffeurs

Depuis `backend/` (`.env` à la racine) :

```bash
.venv/bin/python scripts/ajouter_chauffeurs_digifactory.py --sans-synchro  # dossiers seulement
.venv/bin/python scripts/ajouter_chauffeurs_digifactory.py                 # dossiers puis synchro
```

Un dossier `DIGI_<nr>` par contact, posé en SASU à l'IS sur l'année civile,
forme reprise de Sirene quand le contact a un SIREN. Le reste de la
configuration est à confirmer par le dirigeant (AXE-730). La suite du
chemin vers un premier mois exporté : AXE-727 à AXE-733.

## 5. Lancer l'application

Commandes : [backend/README.md](../backend/README.md), section « Lancer
l'API de démo ». Après un `git pull`, `alembic upgrade head` avant l'API.
Le CORS n'accepte que `http://localhost:3000` ; `DATABASE_URL_WEB` doit
être défini, sinon chaque requête répond 500.

## 6. Risques

| Risque | Parade |
|---|---|
| Les données de vrais chauffeurs vivent dans la même base que le développement | Plus de chemin applicatif qui lève les verrous ; migrations appliquées seulement après revue. Sauvegardes et restauration testée : AXE-811. Isolation stricte de la production : AXE-810 |
| Le dossier de Sophie pollue les chiffres de Serenity | Le nommer et l'exclure à la main des bilans du pilote ; un drapeau « dossier de test » est à prévoir si cela gêne |
| Le mode expert n'a pas encore sa garde juridique | Ne pas l'ouvrir à Serenity avant AXE-800 (doc 02 §2.3) |
