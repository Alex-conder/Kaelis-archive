"""
Deep functional tests for KGCausalEngine.
Covers: observational data extraction, causal discovery (PC + fallback), intervention simulation.
"""

import pytest
import sqlite3

from core.kg_causal import KGCausalEngine, CausalDiscoveryResult, InterventionResult


@pytest.fixture
def temp_db(tmp_path):
    path = tmp_path / "test_graph.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE kg_relations (
                id INTEGER PRIMARY KEY,
                source TEXT,
                target TEXT,
                relation TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE kg_entities (
                id INTEGER PRIMARY KEY,
                name TEXT,
                type TEXT
            )
        """)
        # Insert test data: A -> B -> C, A -> D
        conn.executemany(
            "INSERT INTO kg_relations (source, target, relation) VALUES (?, ?, ?)",
            [
                ("A", "B", "uses"),
                ("B", "C", "requires"),
                ("A", "D", "contains"),
                ("D", "C", "depends"),
            ],
        )
        conn.executemany(
            "INSERT INTO kg_entities (name, type) VALUES (?, ?)",
            [("A", "Concept"), ("B", "Concept"), ("C", "Concept"), ("D", "Concept")],
        )
    return str(path)


class TestDiscovery:
    def test_discover_returns_result(self, temp_db):
        engine = KGCausalEngine(db_path=temp_db)
        result = engine.discover()
        assert isinstance(result, CausalDiscoveryResult)
        assert len(result.nodes) >= 3
        assert result.method in ("pc", "heuristic_dag")

    def test_fallback_dag_resolves_cycles(self, temp_db):
        # Add a cycle
        with sqlite3.connect(temp_db) as conn:
            conn.execute("INSERT INTO kg_relations (source, target, relation) VALUES (?, ?, ?)",
                        ("C", "A", "feeds"))
        engine = KGCausalEngine(db_path=temp_db)
        result = engine.discover()
        # PC or fallback should return a valid structure
        assert len(result.nodes) >= 3
        # If edges exist, verify no cycles (for heuristic_dag)
        if result.edges and result.method == "heuristic_dag":
            adj = {n: [] for n in result.nodes}
            for e in result.edges:
                adj[e["source"]].append(e["target"])

            def has_cycle(start):
                visited = set()
                stack = [start]
                while stack:
                    node = stack.pop()
                    if node == start and node in visited:
                        return True
                    if node not in visited:
                        visited.add(node)
                        stack.extend(adj.get(node, []))
                return False

            for n in result.nodes:
                assert not has_cycle(n)

    def test_empty_kg_returns_note(self, tmp_path):
        path = tmp_path / "empty.db"
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE kg_relations (source TEXT, target TEXT, relation TEXT)")
        engine = KGCausalEngine(db_path=str(path))
        result = engine.discover()
        assert result.note != ""


class TestIntervention:
    def test_intervene_on_existing_node(self, temp_db):
        engine = KGCausalEngine(db_path=temp_db)
        discovered = engine.discover()
        result = engine.intervene("A", "remove", discovered=discovered)
        assert isinstance(result, InterventionResult)
        assert result.target_node == "A"
        assert result.intervention_type == "remove"
        assert result.cascade_depth >= 0

    def test_intervene_on_missing_node(self, temp_db):
        engine = KGCausalEngine(db_path=temp_db)
        result = engine.intervene("NonExistent", "remove")
        assert "not found" in result.note.lower() or "Target node not found" in result.note
