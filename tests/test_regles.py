import pytest

from plm.regles import descendants, verifier_transition
from plm.seed_data import creer_base


@pytest.fixture
def conn(tmp_path):
    """Crée une base de test neuve dans un dossier temporaire, pour chaque test."""
    connexion = creer_base(str(tmp_path / "test.db"))
    yield connexion
    connexion.close()


def test_descendants_moteur(conn):
    resultat = descendants(conn, "A-100", "A")
    assert len(resultat) == 8
    assert ("P-112", "A") in resultat


def test_batterie_publiable(conn):
    autorise, raisons = verifier_transition(conn, "A-200", "A", "Publié")
    assert autorise is True
    assert raisons == []


def test_moteur_bloque(conn):
    autorise, raisons = verifier_transition(conn, "A-100", "A", "Publié")
    assert autorise is False
    assert len(raisons) == 3


def test_train_avant_bloque_par_piece_obsolete(conn):
    autorise, raisons = verifier_transition(conn, "A-300", "A", "Publié")
    assert autorise is False
    assert any("P-312/A" in raison for raison in raisons)

def test_piece_publiee_ne_revient_pas_en_arriere(conn):
    autorise, raisons = verifier_transition(conn, "S-120", "B", "En cours")
    assert autorise is False
    assert len(raisons) == 1