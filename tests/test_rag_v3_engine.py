"""
Deep functional tests for RAGv3Engine.
Covers: entity extraction, strategy routing, response structure.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from core.rag_v3_engine import RAGv3Engine, RAGStrategy, RAGResponse, RAGContext


class TestEntityExtraction:
    def test_extract_chinese_entities(self):
        engine = RAGv3Engine()
        entities = engine._extract_entities_from_query("代谢物具有抗氧化功能")
        # regex matches contiguous Chinese chars (2+), not word segmentation
        assert any("代谢物" in e for e in entities)
        assert any("抗氧化" in e for e in entities)
        assert any("功能" in e for e in entities)

    def test_extract_english_entities(self):
        engine = RAGv3Engine()
        entities = engine._extract_entities_from_query("What is ATP metabolism")
        assert "ATP" in entities
        assert "metabolism" in entities

    def test_extract_mixed_entities(self):
        engine = RAGv3Engine()
        entities = engine._extract_entities_from_query("ATP代谢与能量转换")
        assert "ATP" in entities
        assert any("代谢" in e for e in entities)
        assert any("能量转换" in e for e in entities)

    def test_extract_empty_query(self):
        engine = RAGv3Engine()
        entities = engine._extract_entities_from_query("")
        assert entities == []

    def test_extract_limits_to_five(self):
        engine = RAGv3Engine()
        entities = engine._extract_entities_from_query("A B C D E F G H I J")
        assert len(entities) <= 5


class TestStrategyRouting:
    @pytest.mark.asyncio
    async def test_naive_strategy_returns_response(self):
        engine = RAGv3Engine()
        with patch("core.response_generator.ResponseGenerator") as MockRG:
            mock_rg = MagicMock()
            mock_rg.generate.return_value = {
                "reply": "test reply",
                "trace_id": "trc-1",
                "memory_context": {},
                "safety_check": {"overall_level": "safe"},
            }
            MockRG.return_value = mock_rg

            result = await engine.query("hello", strategy=RAGStrategy.NAIVE)
            assert result.reply == "test reply"
            assert result.strategy == RAGStrategy.NAIVE
            assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_unknown_strategy_fallback(self):
        engine = RAGv3Engine()
        with patch("core.response_generator.ResponseGenerator") as MockRG:
            mock_rg = MagicMock()
            mock_rg.generate.return_value = {"reply": "fallback", "memory_context": {}}
            MockRG.return_value = mock_rg

            result = await engine.query("hello", strategy="unknown")
            assert result.reply == "fallback"

    @pytest.mark.asyncio
    async def test_query_error_handling(self):
        engine = RAGv3Engine()
        with patch("core.response_generator.ResponseGenerator") as MockRG:
            mock_rg = MagicMock()
            mock_rg.generate.side_effect = RuntimeError("LLM failed")
            MockRG.return_value = mock_rg

            result = await engine.query("hello", strategy=RAGStrategy.NAIVE)
            assert "错误" in result.reply
            assert result.confidence == 0.0


class TestResponseStructure:
    def test_rag_response_to_dict(self):
        ctx = RAGContext(query="q1", memory_context={"k": "v"})
        resp = RAGResponse(
            reply="answer",
            strategy=RAGStrategy.GRAPH_RAG,
            trace_id="trc-1",
            confidence=0.9,
            rag_context=ctx,
        )
        d = resp.to_dict()
        assert d["reply"] == "answer"
        assert d["strategy"] == RAGStrategy.GRAPH_RAG
        assert d["confidence"] == 0.9
        assert d["rag_context"]["query"] == "q1"

    def test_extract_sources_from_memory(self):
        engine = RAGv3Engine()
        sources = engine._extract_sources({
            "identity_summary": "user is a researcher",
            "episodic_count": 5,
            "semantic_count": 3,
        })
        assert len(sources) == 3
        assert any(s["layer"] == "L0" for s in sources)
        assert any(s["layer"] == "L2" for s in sources)
        assert any(s["layer"] == "L3" for s in sources)

    def test_format_kg_subgraph(self):
        engine = RAGv3Engine()
        subgraph = [
            {"subject": "A", "predicate": "relates_to", "object": "B"},
            {"subject": "C", "predicate": "is_a", "object": "D"},
        ]
        text = engine._format_kg_subgraph(subgraph)
        assert "A" in text
        assert "relates_to" in text
        assert "B" in text
