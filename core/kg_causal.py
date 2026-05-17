"""
KGCausalEngine — Causal Graph Discovery & Intervention Simulation

Direction 2: Causal Graph (intervention simulation).

Uses causal-learn (PC algorithm) on KG-derived observational data
to discover causal structure, then simulates do-calculus interventions.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CausalDiscoveryResult:
    """因果发现结果"""
    nodes: List[str]
    edges: List[Dict[str, Any]]  # [{"source", "target", "confidence"}]
    adjacency_matrix: List[List[int]]
    method: str = "pc"
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "adjacency_matrix": self.adjacency_matrix,
            "method": self.method,
            "note": self.note,
        }


@dataclass
class InterventionResult:
    """干预模拟结果"""
    target_node: str
    intervention_type: str  # "remove" | "strengthen" | "modify"
    affected_nodes: List[str]
    unaffected_nodes: List[str]
    cascade_depth: int
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_node": self.target_node,
            "intervention_type": self.intervention_type,
            "affected_nodes": self.affected_nodes,
            "unaffected_nodes": self.unaffected_nodes,
            "cascade_depth": self.cascade_depth,
            "note": self.note,
        }


class KGCausalEngine:
    """
    KG 因果引擎。

    1. 从 kg_relations 构建观测数据矩阵
    2. 使用 PC 算法发现因果 DAG
    3. 模拟干预效果（基于 DAG 的下游传播）
    """

    def __init__(self, db_path: Optional[str] = None):
        import os
        from pathlib import Path
        data_dir = os.environ.get("KAELIS_DATA_DIR", "data")
        self.db_path = db_path or str(Path(data_dir) / "kaelis_graph.db")

    def _load_relations(self, limit: int = 500) -> List[Dict[str, Any]]:
        """加载关系数据。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT source, target, relation FROM kg_relations LIMIT ?",
                    (limit,),
                ).fetchall()
            return [{"source": r["source"], "target": r["target"], "relation": r["relation"]} for r in rows]
        except Exception as e:
            logger.error(f"[KGCausal] load_relations failed: {e}")
            return []

    def _build_observational_matrix(
        self,
        relations: List[Dict[str, Any]],
        min_edge_count: int = 2,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        将关系列表转换为观测数据矩阵。

        策略：选取出现频率 >= min_edge_count 的实体作为变量，
        每个样本是一条关系，特征为 [source_onehot, target_onehot, relation_encoded]。
        为了因果发现，我们构建实体共现矩阵并使用 PC 算法。
        """
        # Count entity frequencies
        freq: Dict[str, int] = {}
        for r in relations:
            freq[r["source"]] = freq.get(r["source"], 0) + 1
            freq[r["target"]] = freq.get(r["target"], 0) + 1

        # Select top entities by frequency
        entities = [name for name, count in sorted(freq.items(), key=lambda x: x[1], reverse=True) if count >= min_edge_count]
        if len(entities) < 3:
            # Fallback: take all entities
            entities = list(freq.keys())
        entities = entities[:50]  # cap at 50 for performance
        entity_idx = {e: i for i, e in enumerate(entities)}

        # Build co-occurrence as proxy for observational data
        # Each row: binary vector of which entities are involved in a relation
        data = []
        for r in relations:
            src = r["source"]
            tgt = r["target"]
            if src in entity_idx and tgt in entity_idx:
                row = [0] * len(entities)
                row[entity_idx[src]] = 1
                row[entity_idx[tgt]] = 1
                data.append(row)

        if not data:
            return np.zeros((1, len(entities))), entities

        return np.array(data), entities

    def discover(
        self,
        min_edge_count: int = 2,
        alpha: float = 0.05,
    ) -> CausalDiscoveryResult:
        """
        使用 PC 算法发现因果结构。

        Args:
            min_edge_count: 实体最小出现次数才被纳入分析
            alpha: 条件独立性检验显著性水平
        """
        relations = self._load_relations()
        if not relations:
            return CausalDiscoveryResult(
                nodes=[], edges=[], adjacency_matrix=[],
                note="No relations found in KG",
            )

        data, entities = self._build_observational_matrix(relations, min_edge_count)
        n_vars = len(entities)

        if n_vars < 3 or data.shape[0] < n_vars:
            # Not enough data for PC — fallback to correlation-based heuristic DAG
            return self._fallback_dag(relations, entities)

        try:
            from causallearn.search.ConstraintBased.PC import pc
            from causallearn.utils.cit import fisherz

            cg = pc(data, alpha, fisherz, node_names=entities)
            adj = cg.G.graph  # numpy array

            edges = []
            for i in range(n_vars):
                for j in range(n_vars):
                    if adj[i, j] != 0 and i != j:
                        edges.append({
                            "source": entities[i],
                            "target": entities[j],
                            "confidence": 0.8,  # PC doesn't give confidence directly
                        })

            # Convert adjacency to int matrix
            adj_matrix = adj.astype(int).tolist()

            return CausalDiscoveryResult(
                nodes=entities,
                edges=edges,
                adjacency_matrix=adj_matrix,
                method="pc",
                note=f"Discovered from {data.shape[0]} observations, {n_vars} variables",
            )

        except Exception as e:
            logger.warning(f"[KGCausal] PC discovery failed ({e}), falling back to heuristic")
            return self._fallback_dag(relations, entities)

    def _fallback_dag(
        self,
        relations: List[Dict[str, Any]],
        entities: List[str],
    ) -> CausalDiscoveryResult:
        """当数据不足时，使用启发式构建 DAG（基于关系方向性 + 拓扑排序）。"""
        import networkx as nx

        G = nx.DiGraph()
        for e in entities:
            G.add_node(e)

        # Heuristic direction rules
        for r in relations:
            src, tgt = r["source"], r["target"]
            rel = (r["relation"] or "").lower()
            if src not in entities or tgt not in entities:
                continue

            # Direction heuristics
            if any(kw in rel for kw in ("uses", "depends", "requires", "has", "contains", "owns")):
                G.add_edge(src, tgt)
            elif any(kw in rel for kw in ("is_a", "subclass", "type_of", "part_of", "belongs")):
                G.add_edge(tgt, src)  # parent -> child
            else:
                G.add_edge(src, tgt)  # default: source -> target

        # Break cycles using feedback arc set approximation
        try:
            cycles = list(nx.simple_cycles(G))
            removed = set()
            for cycle in cycles:
                if len(cycle) > 1:
                    # Remove the edge with lowest betweenness (least central)
                    for i in range(len(cycle)):
                        u, v = cycle[i], cycle[(i + 1) % len(cycle)]
                        if (u, v) not in removed:
                            G.remove_edge(u, v)
                            removed.add((u, v))
                            break
        except Exception:
            pass

        nodes = list(G.nodes())
        edges = [{"source": u, "target": v, "confidence": 0.6} for u, v in G.edges()]

        # Build adjacency matrix
        idx = {n: i for i, n in enumerate(nodes)}
        adj = [[0] * len(nodes) for _ in range(len(nodes))]
        for u, v in G.edges():
            adj[idx[u]][idx[v]] = 1

        return CausalDiscoveryResult(
            nodes=nodes,
            edges=edges,
            adjacency_matrix=adj,
            method="heuristic_dag",
            note="Fallback heuristic DAG (insufficient data for PC algorithm)",
        )

    def intervene(
        self,
        target_node: str,
        intervention_type: str = "remove",
        discovered: Optional[CausalDiscoveryResult] = None,
    ) -> InterventionResult:
        """
        模拟对目标节点的干预（do-calculus 近似）。

        Args:
            target_node: 被干预的实体名称
            intervention_type: "remove" | "strengthen" | "modify"
            discovered: 预发现的因果结构（可选，会重新计算）
        """
        if discovered is None:
            discovered = self.discover()

        nodes = discovered.nodes
        edges = discovered.edges
        if target_node not in nodes:
            return InterventionResult(
                target_node=target_node,
                intervention_type=intervention_type,
                affected_nodes=[],
                unaffected_nodes=[],
                cascade_depth=0,
                note="Target node not found in causal graph",
            )

        # Build adjacency
        adj: Dict[str, List[str]] = {n: [] for n in nodes}
        for e in edges:
            adj[e["source"]].append(e["target"])

        # BFS downstream from target to find affected nodes
        affected: Set[str] = set()
        queue = [(target_node, 0)]
        max_depth = 0

        while queue:
            current, depth = queue.pop(0)
            if current in affected:
                continue
            affected.add(current)
            max_depth = max(max_depth, depth)
            for child in adj.get(current, []):
                if child not in affected:
                    queue.append((child, depth + 1))

        affected.discard(target_node)  # exclude self
        unaffected = [n for n in nodes if n not in affected and n != target_node]

        note = f"Intervention '{intervention_type}' on '{target_node}' affects {len(affected)} downstream nodes"
        if intervention_type == "remove":
            note += ". All outgoing causal paths are severed."
        elif intervention_type == "strengthen":
            note += ". Effects are amplified along outgoing paths."

        return InterventionResult(
            target_node=target_node,
            intervention_type=intervention_type,
            affected_nodes=sorted(affected),
            unaffected_nodes=sorted(unaffected),
            cascade_depth=max_depth,
            note=note,
        )


# ------------------------------------------------------------------ #
# Singleton
# ------------------------------------------------------------------ #
_kg_causal_instance: Optional[KGCausalEngine] = None


def get_kg_causal_engine() -> KGCausalEngine:
    global _kg_causal_instance
    if _kg_causal_instance is None:
        _kg_causal_instance = KGCausalEngine()
    return _kg_causal_instance
