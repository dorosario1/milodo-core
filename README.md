#  MILODO CORE V2

Agent de développement autonome évolutif.

## Description projet

MILODO CORE V2 est un noyau local pour scanner des projets, planifier des objectifs, exécuter des tâches contrôlées, gérer une mémoire minimale et charger des skills dynamiques.

## Architecture modules

- `milodo.py` : CLI unifiée.
- `project_scanner.py` : détection locale de projets.
- `state_recall.py` : état minimal des projets.
- `planner.py` : transformation d'objectifs en plans.
- `dag_engine.py` : exécution DAG minimale.
- `memory.py` : mémoire persistante locale.
- `skill_loader.py` : chargement dynamique des skills.
- `chat_server.py` : serveur chat local HTTP.
- `skills/` : skills dynamiques.

## Commandes CLI

```bash
python milodo.py scan
python milodo.py status
python milodo.py plan "objectif"
python milodo.py run "objectif"
python milodo.py remember "type" "contenu"
python milodo.py memory "query"
python milodo.py skills
python milodo.py chat
```

## Système de skills

Les skills sont des modules Python placés dans `skills/`. Chaque skill valide expose au minimum `SKILL_NAME` et `SKILL_DESCRIPTION`. Le chargeur dynamique liste les skills chargées, invalides et les erreurs.

## Auto-augmentation

Le chat local peut recevoir une demande d'apprentissage sous forme textuelle, générer une nouvelle skill minimale et la charger via le système de skills.

## Installation

```bash
cd milodo-core
python -m py_compile milodo.py
```

## Prérequis

Python 3.10+

Ollama optionnel

Clé OpenAI optionnelle

## Structure dossiers

```txt
milodo-core/
  milodo.py
  chat_server.py
  chat.html
  skill_loader.py
  skills/
    __init__.py
```

## Exemple utilisation rapide

```bash
python milodo.py scan
python milodo.py status
python milodo.py chat
```
