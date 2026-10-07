import sqlite3

from plm.seed_data import TRANSITIONS_AUTORISEES


def enfants_directs(conn: sqlite3.Connection, reference: str, revision: str) -> list[tuple[str, str]]:
    """Renvoie la liste des (référence, révision) des enfants directs d'une pièce."""
    lignes = conn.execute(
        "SELECT enfant_ref, enfant_rev FROM structure WHERE parent_ref = ? AND parent_rev = ?",
        (reference, revision),
    ).fetchall()
    return lignes


def descendants(conn: sqlite3.Connection, reference: str, revision: str) -> list[tuple[str, str]]:
    """Renvoie tous les descendants d'une pièce, à tous les niveaux."""
    resultat = []
    for enfant_ref, enfant_rev in enfants_directs(conn, reference, revision):
        resultat.append((enfant_ref, enfant_rev))
        resultat.extend(descendants(conn, enfant_ref, enfant_rev))
    return resultat


def etat_piece(conn: sqlite3.Connection, reference: str, revision: str) -> str:
    """Renvoie l'état actuel d'une pièce."""
    ligne = conn.execute(
        "SELECT etat FROM pieces WHERE reference = ? AND revision = ?",
        (reference, revision),
    ).fetchone()
    return ligne[0]


def verifier_transition(conn, reference, revision, etat_cible) -> tuple[bool, list[str]]:
    """Indique si la transition est autorisée et, sinon, la liste des raisons."""
    raisons = []
    etat_actuel = etat_piece(conn, reference, revision)

    # Règle 1 : la transition doit faire partie des transitions autorisées
    if etat_cible not in TRANSITIONS_AUTORISEES[etat_actuel]:
        raisons.append(f"{reference}/{revision} est '{etat_actuel}' : passage à '{etat_cible}' interdit.")

    # Règle 2 : pour publier, tous les descendants doivent être publiés
    if etat_cible == "Publié":
        for ref, rev in descendants(conn, reference, revision):
            etat = etat_piece(conn, ref, rev)
            if etat not in ("Publié", "Obsolète"):
                raisons.append(f"{ref}/{rev} est '{etat}' : il doit être publié avant.")

    # Règle 3 : aucun descendant ne doit être obsolète
    for ref, rev in descendants(conn, reference, revision):
        if etat_piece(conn, ref, rev) == "Obsolète":
            raisons.append(f"{ref}/{rev} est obsolète : il doit être remplacé par une révision à jour.")

    return len(raisons) == 0, raisons


if __name__ == "__main__":
    conn = sqlite3.connect("plm.db")
    print(verifier_transition(conn, "A-200", "A", "Publié"))
    print(verifier_transition(conn, "A-100", "A", "Publié"))
    print(verifier_transition(conn, "A-300", "A", "Publié"))