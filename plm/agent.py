import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from plm.outils import (
    cas_emploi,
    consulter_piece,
    effectuer_transition,
    lister_descendants,
    rechercher_pieces,
    verifier_transition,
)

load_dotenv()

OUTILS = [rechercher_pieces, consulter_piece, lister_descendants, cas_emploi, verifier_transition, effectuer_transition]

PROMPT_SYSTEME = """Tu es un assistant de gestion du cycle de vie produit (PLM) pour des ingénieurs.
Règles :
- Appuie-toi TOUJOURS sur les outils pour connaître l'état d'une pièce ; n'invente jamais une information.
- Une pièce est identifiée par une référence (ex : A-100) et une révision (ex : A). Si la révision n'est pas précisée, utilise A.
- Si l'utilisateur désigne une pièce par son nom, retrouve sa référence avec rechercher_pieces.
- Pour savoir si une transition est possible, utilise verifier_transition : c'est lui qui applique les règles métier.
- Pour changer l'état d'une pièce, vérifie d'abord la transition, puis appelle effectuer_transition :
  le système demandera automatiquement la validation de l'utilisateur avant toute modification.
- Réponds en français, de façon concise, en expliquant clairement les raisons d'un éventuel blocage.
- Ne demande pas toi-même de confirmation avant effectuer_transition : le système s'en charge.
"""


def construire_agent(modele=None):
    """Construit le graphe de l'agent. Le modèle peut être remplacé (utile pour les tests)."""
    if modele is None:
        modele = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    modele_avec_outils = modele.bind_tools(OUTILS)

    def appeler_modele(state: MessagesState):
        messages = [SystemMessage(PROMPT_SYSTEME)] + state["messages"]
        return {"messages": [modele_avec_outils.invoke(messages)]}

    def aiguiller(state: MessagesState) -> Literal["outils", "validation", "__end__"]:
        """Décide de l'étape suivante après une réponse du modèle."""
        dernier = state["messages"][-1]
        if not dernier.tool_calls:
            return END
        if any(appel["name"] == "effectuer_transition" for appel in dernier.tool_calls):
            return "validation"
        return "outils"

    def valider(state: MessagesState) -> Command[Literal["outils", "agent"]]:
        """Met le graphe en pause et demande l'accord de l'utilisateur avant toute modification."""
        dernier = state["messages"][-1]
        demandes = [a["args"] for a in dernier.tool_calls if a["name"] == "effectuer_transition"]
        resume = ", ".join(f"{d['reference']}/{d['revision']} vers '{d['etat_cible']}'" for d in demandes)
        reponse = interrupt(f"L'agent veut passer {resume}. Confirmez-vous ? (oui/non)")

        if str(reponse).strip().lower() in ("oui", "o", "yes", "y"):
            return Command(goto="outils")

        refus = [
            ToolMessage(content="Refusé par l'utilisateur : aucune modification n'a été effectuée.", tool_call_id=a["id"])
            for a in dernier.tool_calls
        ]
        return Command(goto="agent", update={"messages": refus})

    graphe = StateGraph(MessagesState)
    graphe.add_node("agent", appeler_modele)
    graphe.add_node("outils", ToolNode(OUTILS))
    graphe.add_node("validation", valider)
    graphe.add_edge(START, "agent")
    graphe.add_conditional_edges("agent", aiguiller)
    graphe.add_edge("outils", "agent")
    return graphe.compile(checkpointer=InMemorySaver())


def afficher_outils(messages):
    """Affiche les outils appelés, pour suivre le raisonnement de l'agent."""
    for message in messages:
        if isinstance(message, AIMessage):
            for appel in message.tool_calls:
                print(f"  [outil] {appel['name']}({appel['args']})")


if __name__ == "__main__":
    agent = construire_agent()
    config = {"configurable": {"thread_id": "session-1"}}
    print("Assistant PLM - tapez 'quitter' pour sortir.")
    while True:
        question = input("\nVous : ")
        if question.strip().lower() in ("quitter", "exit"):
            break
        debut = len(agent.get_state(config).values.get("messages", []))
        resultat = agent.invoke({"messages": [HumanMessage(question)]}, config)

        # Tant que le graphe est en pause, on demande la validation à l'utilisateur
        while "__interrupt__" in resultat:
            afficher_outils(resultat["messages"][debut:])
            debut = len(resultat["messages"])
            decision = input(f"\n>>> {resultat['__interrupt__'][0].value} ")
            resultat = agent.invoke(Command(resume=decision), config)

        afficher_outils(resultat["messages"][debut:])
        print(f"\nAgent : {resultat['messages'][-1].content}")