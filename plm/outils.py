import httpx
from langchain_core.tools import tool

URL_API = "http://127.0.0.1:8000"
client = httpx.Client(base_url=URL_API, timeout=10)


def _reponse(r: httpx.Response):
    """Renvoie le JSON de l'API, ou un message d'erreur lisible par l'agent."""
    if r.status_code == 404:
        return {"erreur": r.json()["detail"]}
    if r.status_code == 409:
        return {"erreur": "Transition refusée", "raisons": r.json()["detail"]}
    r.raise_for_status()
    return r.json()


@tool
def consulter_piece(reference: str, revision: str) -> dict:
    """Donne le nom, le type et l'état d'une pièce à partir de sa référence (ex : A-100) et de sa révision (ex : A)."""
    return _reponse(client.get(f"/pieces/{reference}/{revision}"))


@tool
def lister_descendants(reference: str, revision: str) -> list | dict:
    """Liste tous les composants d'une pièce ou d'un assemblage, à tous les niveaux, avec leur état."""
    return _reponse(client.get(f"/pieces/{reference}/{revision}/descendants"))


@tool
def verifier_transition(reference: str, revision: str, etat_cible: str) -> dict:
    """Vérifie, SANS rien modifier, si une pièce peut passer à un nouvel état
    ('En cours', 'Gelé', 'Publié' ou 'Obsolète') et donne les raisons d'un éventuel blocage."""
    return _reponse(client.get(f"/pieces/{reference}/{revision}/verification", params={"etat_cible": etat_cible}))


@tool
def effectuer_transition(reference: str, revision: str, etat_cible: str) -> dict:
    """Change réellement l'état d'une pièce. À n'utiliser qu'après accord explicite de l'utilisateur."""
    return _reponse(client.post(f"/pieces/{reference}/{revision}/transition", json={"etat_cible": etat_cible}))


OUTILS = [consulter_piece, lister_descendants, verifier_transition, effectuer_transition]

if __name__ == "__main__":
    print(consulter_piece.invoke({"reference": "A-100", "revision": "A"}))
    print(verifier_transition.invoke({"reference": "A-100", "revision": "A", "etat_cible": "Publié"}))
    print(consulter_piece.invoke({"reference": "X-999", "revision": "A"}))