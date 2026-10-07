import sqlite3
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from plm.regles import descendants, verifier_transition

CHEMIN_BASE = "plm.db"
Etat = Literal["En cours", "Gelé", "Publié", "Obsolète"]

app = FastAPI(title="Mini-PLM", description="API de gestion du cycle de vie des pièces")


def get_conn():
    """Ouvre une connexion à la base pour chaque requête, puis la referme."""
    conn = sqlite3.connect(CHEMIN_BASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def lire_piece(conn, reference: str, revision: str) -> dict:
    """Renvoie une pièce sous forme de dictionnaire, ou une erreur 404 si elle n'existe pas."""
    ligne = conn.execute(
        "SELECT * FROM pieces WHERE reference = ? AND revision = ?", (reference, revision)
    ).fetchone()
    if ligne is None:
        raise HTTPException(status_code=404, detail=f"Pièce {reference}/{revision} introuvable.")
    return dict(ligne)


class DemandeTransition(BaseModel):
    etat_cible: Etat


@app.get("/pieces")
def lister_pieces(conn=Depends(get_conn)):
    lignes = conn.execute("SELECT * FROM pieces ORDER BY reference, revision").fetchall()
    return [dict(ligne) for ligne in lignes]


@app.get("/pieces/{reference}/{revision}")
def consulter_piece(reference: str, revision: str, conn=Depends(get_conn)):
    return lire_piece(conn, reference, revision)


@app.get("/pieces/{reference}/{revision}/descendants")
def lister_descendants(reference: str, revision: str, conn=Depends(get_conn)):
    lire_piece(conn, reference, revision)
    return [lire_piece(conn, ref, rev) for ref, rev in descendants(conn, reference, revision)]


@app.get("/pieces/{reference}/{revision}/verification")
def verifier(reference: str, revision: str, etat_cible: Etat, conn=Depends(get_conn)):
    lire_piece(conn, reference, revision)
    autorise, raisons = verifier_transition(conn, reference, revision, etat_cible)
    return {"autorise": autorise, "raisons": raisons}


@app.post("/pieces/{reference}/{revision}/transition")
def effectuer_transition(reference: str, revision: str, demande: DemandeTransition, conn=Depends(get_conn)):
    lire_piece(conn, reference, revision)
    autorise, raisons = verifier_transition(conn, reference, revision, demande.etat_cible)
    if not autorise:
        raise HTTPException(status_code=409, detail=raisons)
    conn.execute(
        "UPDATE pieces SET etat = ? WHERE reference = ? AND revision = ?",
        (demande.etat_cible, reference, revision),
    )
    conn.commit()
    return lire_piece(conn, reference, revision)