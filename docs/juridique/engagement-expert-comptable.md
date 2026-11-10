# Engagement de l'expert-comptable

> Version 2026-11-09, celle que l'expert accepte dans l'application. Projet,
> à relire par un juriste (AXE-813). Le texte qui fait foi est
> `TEXTE_ENGAGEMENT` dans `backend/axelcompta/workflow/expert_comptable.py` :
> toute modification change sa version, et chaque expert l'accepte de
> nouveau. Ce fichier le reprend mot pour mot (vérifié par un test).

## Le texte accepté

> Je, expert-comptable inscrit au tableau de l'Ordre, décide seul et sous ma responsabilité de chaque imputation, annulation ou qualification que je passe dans les dossiers couverts par ma lettre de mission. AxeLCompta est un outil : il ne décide d'aucune écriture et ne vérifie pas mes choix. Chacun de mes changements porte mon nom, son motif et la date ; je ne passe pas de changement sans motif.

## Ce que l'application en fait

- L'expert n'accède au mode expert qu'après avoir été **habilité** par un
  administrateur du portefeuille (nom, cabinet, numéro d'inscription à
  l'Ordre, lettre de mission, dossiers couverts), et après avoir **accepté**
  ce texte. L'acceptation est gardée avec sa version, sa date et l'adresse
  de connexion.
- Il n'agit que sur les dossiers couverts par sa lettre de mission.
- Chaque imputation, annulation ou qualification porte son nom, son motif
  et la date ; le dirigeant voit « Reclassée par [nom], expert-comptable ».
- Il se connecte avec la double authentification.
