"""
Données de démonstration pour l'agent de cycle de vie produit (mini-PLM).

Crée une base SQLite avec :
- une table `pieces`    : une ligne par couple (référence, révision)
- une table `structure` : les liens parent -> enfant (nomenclature / BOM)

Usage :
    python seed_data.py            # crée plm.db et affiche les arborescences
    python seed_data.py autre.db   # chemin personnalisé
"""

import sqlite3
import sys

# --------------------------------------------------------------------------
# Référentiel des états et transitions (configuration métier)
# --------------------------------------------------------------------------
ETATS = ["En cours", "Gelé", "Publié", "Obsolète"]

TRANSITIONS_AUTORISEES = {
    "En cours": ["Gelé"],
    "Gelé": ["En cours", "Publié"],   # dégel possible avant publication
    "Publié": ["Obsolète"],           # pas de retour en arrière après publication
    "Obsolète": [],
}

# --------------------------------------------------------------------------
# Pièces : (référence, révision, nom, type, état, remplacée_par)
# type : "Assemblage", "Sous-ensemble" ou "Pièce"
# --------------------------------------------------------------------------
PIECES = [
    # Assemblage 1 : moteur électrique -> BLOQUÉ (sous-ensemble et pièce gelés)
    ("A-100", "A", "Moteur électrique", "Assemblage", "En cours", None),
    ("S-110", "A", "Stator", "Sous-ensemble", "Gelé", None),
    ("P-111", "A", "Bobinage cuivre", "Pièce", "Publié", None),
    ("P-112", "A", "Tôles magnétiques", "Pièce", "Gelé", None),
    ("S-120", "A", "Rotor", "Sous-ensemble", "Obsolète", "B"),
    ("S-120", "B", "Rotor", "Sous-ensemble", "Publié", None),
    ("P-121", "A", "Arbre de rotor", "Pièce", "Publié", None),
    ("P-122", "A", "Aimants permanents", "Pièce", "Publié", None),
    ("P-130", "A", "Carter aluminium", "Pièce", "Publié", None),

    # Assemblage 2 : module batterie -> PUBLIABLE (cas nominal)
    ("A-200", "A", "Module batterie", "Assemblage", "Gelé", None),
    ("S-210", "A", "Pack de cellules", "Sous-ensemble", "Publié", None),
    ("P-211", "A", "Cellule lithium-ion", "Pièce", "Publié", None),
    ("S-220", "A", "Système de gestion batterie (BMS)", "Sous-ensemble", "Publié", None),
    ("P-221", "A", "Carte électronique BMS", "Pièce", "Publié", None),
    ("P-222", "A", "Capteur de température", "Pièce", "Publié", None),
    ("P-230", "A", "Boîtier batterie", "Pièce", "Publié", None),

    # Assemblage 3 : train avant -> BLOQUÉ (sous-ensemble en cours + pièce obsolète utilisée)
    ("A-300", "A", "Train avant", "Assemblage", "Gelé", None),
    ("S-310", "A", "Bras de suspension", "Sous-ensemble", "En cours", None),
    ("P-311", "A", "Rotule", "Pièce", "Publié", None),
    ("P-312", "A", "Silentbloc", "Pièce", "Obsolète", "B"),
    ("P-312", "B", "Silentbloc", "Pièce", "Publié", None),
    ("P-320", "A", "Disque de frein", "Pièce", "Publié", None),

    # Pièce orpheline : utilisée dans aucun assemblage
    ("P-400", "A", "Connecteur haute tension", "Pièce", "En cours", None),
]

# --------------------------------------------------------------------------
# Structure : (réf. parent, rév. parent, réf. enfant, rév. enfant, quantité)
# --------------------------------------------------------------------------
STRUCTURE = [
    # Moteur électrique
    ("A-100", "A", "S-110", "A", 1),
    ("A-100", "A", "S-120", "B", 1),   # utilise bien la révision B (à jour)
    ("A-100", "A", "P-130", "A", 1),
    ("S-110", "A", "P-111", "A", 3),
    ("S-110", "A", "P-112", "A", 48),
    ("S-110", "A", "P-222", "A", 1),   # pièce partagée avec le BMS
    ("S-120", "B", "P-121", "A", 1),
    ("S-120", "B", "P-122", "A", 8),
    ("S-120", "A", "P-121", "A", 1),   # ancienne révision du rotor
    ("S-120", "A", "P-122", "A", 6),

    # Module batterie
    ("A-200", "A", "S-210", "A", 1),
    ("A-200", "A", "S-220", "A", 1),
    ("A-200", "A", "P-230", "A", 1),
    ("S-210", "A", "P-211", "A", 96),
    ("S-220", "A", "P-221", "A", 1),
    ("S-220", "A", "P-222", "A", 4),

    # Train avant
    ("A-300", "A", "S-310", "A", 2),
    ("A-300", "A", "P-320", "A", 2),
    ("S-310", "A", "P-311", "A", 1),
    ("S-310", "A", "P-312", "A", 2),   # utilise encore la révision obsolète A
]

# --------------------------------------------------------------------------
# Scénarios attendus : serviront de base au jeu d'évaluation de l'agent
# --------------------------------------------------------------------------
SCENARIOS = [
    {
        "question": "Peut-on publier le module batterie A-200 ?",
        "attendu": "Oui : A-200 est gelé et tous ses composants, à tous les niveaux, sont publiés.",
    },
    {
        "question": "Peut-on publier le moteur électrique A-100 ?",
        "attendu": "Non : A-100 est en cours (il doit d'abord être gelé), et le stator S-110 "
                   "ainsi que les tôles P-112 sont seulement gelés.",
    },
    {
        "question": "Qu'est-ce qui bloque la publication du train avant A-300 ?",
        "attendu": "Le bras de suspension S-310 est en cours, et il utilise le silentbloc "
                   "P-312 en révision A, obsolète et remplacée par la révision B.",
    },
    {
        "question": "Où est utilisé le capteur de température P-222 ?",
        "attendu": "Dans le stator S-110 (moteur A-100) et dans le BMS S-220 (module batterie A-200).",
    },
    {
        "question": "Peut-on remettre le rotor S-120 révision B en cours ?",
        "attendu": "Non : une pièce publiée ne peut passer qu'à l'état obsolète.",
    },
    {
        "question": "Quelles pièces ne sont utilisées dans aucun assemblage ?",
        "attendu": "Le connecteur haute tension P-400 (ainsi que les révisions obsolètes S-120/A et P-312/A "
                   "selon la définition retenue).",
    },
]


def creer_base(chemin: str = "plm.db") -> sqlite3.Connection:
    """Crée (ou recrée) la base SQLite et y insère les données de démonstration."""
    conn = sqlite3.connect(chemin)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS structure;
        DROP TABLE IF EXISTS pieces;

        CREATE TABLE pieces (
            reference     TEXT NOT NULL,
            revision      TEXT NOT NULL,
            nom           TEXT NOT NULL,
            type          TEXT NOT NULL CHECK (type IN ('Assemblage', 'Sous-ensemble', 'Pièce')),
            etat          TEXT NOT NULL CHECK (etat IN ('En cours', 'Gelé', 'Publié', 'Obsolète')),
            remplacee_par TEXT,
            PRIMARY KEY (reference, revision)
        );

        CREATE TABLE structure (
            parent_ref TEXT NOT NULL,
            parent_rev TEXT NOT NULL,
            enfant_ref TEXT NOT NULL,
            enfant_rev TEXT NOT NULL,
            quantite   INTEGER NOT NULL CHECK (quantite > 0),
            PRIMARY KEY (parent_ref, parent_rev, enfant_ref, enfant_rev),
            FOREIGN KEY (parent_ref, parent_rev) REFERENCES pieces (reference, revision),
            FOREIGN KEY (enfant_ref, enfant_rev) REFERENCES pieces (reference, revision)
        );
        """
    )
    cur.executemany("INSERT INTO pieces VALUES (?, ?, ?, ?, ?, ?)", PIECES)
    cur.executemany("INSERT INTO structure VALUES (?, ?, ?, ?, ?)", STRUCTURE)
    conn.commit()
    return conn


def afficher_arborescence(conn, ref, rev, niveau=0, quantite=1):
    """Affiche la nomenclature d'une pièce de façon récursive (utile pour vérifier les données)."""
    nom, etat = conn.execute(
        "SELECT nom, etat FROM pieces WHERE reference = ? AND revision = ?", (ref, rev)
    ).fetchone()
    prefixe = "    " * niveau + ("└─ " if niveau else "")
    print(f"{prefixe}{ref}/{rev}  {nom}  x{quantite}  [{etat}]")
    for enfant_ref, enfant_rev, qte in conn.execute(
        "SELECT enfant_ref, enfant_rev, quantite FROM structure "
        "WHERE parent_ref = ? AND parent_rev = ? ORDER BY enfant_ref",
        (ref, rev),
    ):
        afficher_arborescence(conn, enfant_ref, enfant_rev, niveau + 1, qte)


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "plm.db"
    conn = creer_base(chemin)
    print(f"Base créée : {chemin} ({len(PIECES)} pièces, {len(STRUCTURE)} liens)\n")
    for ref in ("A-100", "A-200", "A-300"):
        afficher_arborescence(conn, ref, "A")
        print()
    conn.close()
