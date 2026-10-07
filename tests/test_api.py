import sqlite3

import pytest
from fastapi.testclient import TestClient

from plm.api import app, get_conn
from plm.seed_data import creer_base


@pytest.fixture
def client(tmp_path):
    """Client de test branché sur une base temporaire neuve, pour ne jamais toucher plm.db."""
    chemin = str(tmp_path / "test.db")
    creer_base(chemin).close()

    def get_conn_test():
        conn = sqlite3.connect(chemin, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_conn] = get_conn_test
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lister_pieces(client):
    reponse = client.get("/pieces")
    assert reponse.status_code == 200
    assert len(reponse.json()) == 23


def test_piece_inexistante(client):
    reponse = client.get("/pieces/X-999/A")
    assert reponse.status_code == 404


def test_verification_moteur_bloque(client):
    reponse = client.get("/pieces/A-100/A/verification", params={"etat_cible": "Publié"})
    assert reponse.status_code == 200
    assert reponse.json()["autorise"] is False
    assert len(reponse.json()["raisons"]) == 3


def test_publication_batterie(client):
    reponse = client.post("/pieces/A-200/A/transition", json={"etat_cible": "Publié"})
    assert reponse.status_code == 200
    assert reponse.json()["etat"] == "Publié"


def test_transition_refusee(client):
    reponse = client.post("/pieces/A-100/A/transition", json={"etat_cible": "Publié"})
    assert reponse.status_code == 409
    # la pièce n'a pas été modifiée
    assert client.get("/pieces/A-100/A").json()["etat"] == "En cours"


def test_etat_invalide(client):
    reponse = client.post("/pieces/A-100/A/transition", json={"etat_cible": "Terminé"})
    assert reponse.status_code == 422