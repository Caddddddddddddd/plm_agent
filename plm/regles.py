import sqlite3


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


if __name__ == "__main__":
    conn = sqlite3.connect("plm.db")
    print(descendants(conn, "A-100", "A"))