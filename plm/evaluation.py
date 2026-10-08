"""
Jeu d'évaluation de l'agent PLM.

Pose une série de questions à l'agent (avec le vrai modèle), plusieurs fois chacune,
et vérifie automatiquement :
  - qu'il a appelé les bons outils,
  - qu'il n'a rien modifié (aucune demande de transition sur ces questions de lecture),
  - que sa réponse contient les informations attendues.

Usage (l'API doit tourner dans un autre terminal) :
    python -m plm.evaluation               # 3 répétitions par question
    python -m plm.evaluation --repetitions 1
"""

import argparse
import json
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from plm.agent import construire_agent

# Chaque élément de "mots" doit apparaître dans la réponse (insensible à la casse).
# Un tuple signifie "au moins une de ces formulations".
SCENARIOS = [
    {"question": "Peut-on publier le module batterie A-200 ?",
     "outils": ["verifier_transition"], "mots": ["A-200"]},
    {"question": "Peut-on publier le moteur A-100 ?",
     "outils": ["verifier_transition"], "mots": ["S-110", "P-112"]},
    {"question": "Qu'est-ce qui bloque la publication du train avant A-300 ?",
     "outils": ["verifier_transition"], "mots": ["S-310", "P-312"]},
    {"question": "Où est utilisé le capteur P-222 ?",
     "outils": ["cas_emploi"], "mots": ["A-100", "A-200"]},
    {"question": "Peut-on publier le module batterie ?",
     "outils": ["rechercher_pieces", "verifier_transition"], "mots": ["A-200"]},
    {"question": "Quel est l'état du rotor S-120 révision B ?",
     "outils": ["consulter_piece"], "mots": ["publié"]},
    {"question": "Peut-on remettre le rotor S-120 révision B en cours ?",
     "outils": ["verifier_transition"], "mots": ["publié"]},
    {"question": "Quels sont les composants du stator S-110 ?",
     "outils": ["lister_descendants"], "mots": ["P-111", "P-112", "P-222"]},
    {"question": "Dans quels assemblages est utilisé le silentbloc P-312 révision A ?",
     "outils": ["cas_emploi"], "mots": ["S-310", "A-300"]},
    {"question": "Peut-on geler le moteur A-100 ?",
     "outils": ["verifier_transition"], "mots": ["A-100"]},
    {"question": "Le connecteur haute tension est-il utilisé quelque part ?",
     "outils": ["rechercher_pieces", "cas_emploi"], "mots": ["P-400"]},
    {"question": "Quel est l'état de la pièce X-999 ?",
     "outils": ["consulter_piece"], "mots": [("introuvable", "n'existe pas", "aucune pièce")]},
]


def interroger(agent, question: str) -> tuple[list[str], str]:
    """Pose une question dans une conversation neuve ; refuse toute demande de modification."""
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    resultat = agent.invoke({"messages": [HumanMessage(question)]}, config)
    while "__interrupt__" in resultat:
        resultat = agent.invoke(Command(resume="non"), config)
    outils = [a["name"] for m in resultat["messages"] if isinstance(m, AIMessage) for a in m.tool_calls]
    return outils, resultat["messages"][-1].content


def contient(reponse: str, mot) -> bool:
    alternatives = mot if isinstance(mot, tuple) else (mot,)
    return any(a.lower() in reponse.lower() for a in alternatives)


def evaluer(agent, repetitions: int = 3) -> dict:
    essais = []
    for scenario in SCENARIOS:
        for _ in range(repetitions):
            outils, reponse = interroger(agent, scenario["question"])
            bons_outils = all(o in outils for o in scenario["outils"]) and "effectuer_transition" not in outils
            reponse_complete = all(contient(reponse, m) for m in scenario["mots"])
            essais.append({
                "question": scenario["question"],
                "outils_appeles": outils,
                "bons_outils": bons_outils,
                "reponse_complete": reponse_complete,
                "reussi": bons_outils and reponse_complete,
                "reponse": reponse,
            })
            print(f"{'OK ' if bons_outils and reponse_complete else 'KO '} {scenario['question']}  {outils}")

    total = len(essais)
    resume = {
        "essais": total,
        "taux_bons_outils": round(100 * sum(e["bons_outils"] for e in essais) / total, 1),
        "taux_reponses_completes": round(100 * sum(e["reponse_complete"] for e in essais) / total, 1),
        "taux_reussite_global": round(100 * sum(e["reussi"] for e in essais) / total, 1),
    }
    return {"resume": resume, "essais": essais}


if __name__ == "__main__":
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--repetitions", type=int, default=3)
    args = parseur.parse_args()

    resultats = evaluer(construire_agent(), args.repetitions)
    with open("resultats_evaluation.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)

    r = resultats["resume"]
    print(f"\n{len(SCENARIOS)} questions x {args.repetitions} répétitions = {r['essais']} essais")
    print(f"Bons outils appelés   : {r['taux_bons_outils']} %")
    print(f"Réponses complètes    : {r['taux_reponses_completes']} %")
    print(f"Réussite globale      : {r['taux_reussite_global']} %")
    print("Détail enregistré dans resultats_evaluation.json")