import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from plm.outils import consulter_piece, lister_descendants, verifier_transition

load_dotenv()

OUTILS_LECTURE = [consulter_piece, lister_descendants, verifier_transition]

PROMPT_SYSTEME = """Tu es un assistant de gestion du cycle de vie produit (PLM) pour des ingénieurs.
Règles :
- Appuie-toi TOUJOURS sur les outils pour connaître l'état d'une pièce ; n'invente jamais une information.
- Une pièce est identifiée par une référence (ex : A-100) et une révision (ex : A). Si la révision n'est pas précisée, utilise A.
- Pour savoir si une transition est possible, utilise l'outil verifier_transition : c'est lui qui applique les règles métier.
- Réponds en français, de façon concise, en expliquant clairement les raisons d'un éventuel blocage.
"""


def construire_agent(modele=None):
    """Construit le graphe de l'agent. Le modèle peut être remplacé (utile pour les tests)."""
    if modele is None:
        modele = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    modele_avec_outils = modele.bind_tools(OUTILS_LECTURE)

    def appeler_modele(state: MessagesState):
        messages = [SystemMessage(PROMPT_SYSTEME)] + state["messages"]
        return {"messages": [modele_avec_outils.invoke(messages)]}

    graphe = StateGraph(MessagesState)
    graphe.add_node("agent", appeler_modele)
    graphe.add_node("outils", ToolNode(OUTILS_LECTURE))
    graphe.add_edge(START, "agent")
    graphe.add_conditional_edges("agent", tools_condition, {"tools": "outils", END: END})
    graphe.add_edge("outils", "agent")
    return graphe.compile()


if __name__ == "__main__":
    agent = construire_agent()
    historique = []
    print("Assistant PLM - tapez 'quitter' pour sortir.")
    while True:
        question = input("\nVous : ")
        if question.strip().lower() in ("quitter", "exit"):
            break
        historique.append(HumanMessage(question))
        resultat = agent.invoke({"messages": historique})
        # Affiche les outils appelés pendant ce tour, pour voir le raisonnement de l'agent
        for message in resultat["messages"][len(historique):]:
            if isinstance(message, AIMessage):
                for appel in message.tool_calls:
                    print(f"  [outil] {appel['name']}({appel['args']})")
        historique = resultat["messages"]
        print(f"\nAgent : {historique[-1].content}")