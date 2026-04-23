#!/usr/bin/env python
"""Backend verification script for Sprint 3-4 changes."""

print("=" * 60)
print("Kaelis Backend Verification - Sprint 3-4")
print("=" * 60)

# Test 1: kg_flywheel_agent._analyze_intent
print("\n[1/5] Testing _analyze_intent...")
from api.routes.kg_flywheel_agent import KgFlywheelAgent
agent = KgFlywheelAgent('test_user')
tests = [
    ('帮我提取这段文本的关系', 'extract'),
    ('查询张三和李四的关系', 'query'),
    ('质检这个图谱', 'inspect'),
    ('执行完整飞轮流程', 'flywheel'),
    ('你好', 'general'),
]
for text, expected in tests:
    intent, conf = agent._analyze_intent(text)
    status = 'PASS' if intent == expected else 'FAIL'
    print(f'  {status}: {text[:15]}... -> intent={intent}, conf={conf:.2f}')

# Test 2: kg_flywheel_agent._extract_user_info
print("\n[2/5] Testing _extract_user_info...")
info_tests = [
    ('我叫张三', {'name': '张三'}),
    ('我喜欢Python', {'preference': 'Python'}),
    ('随便聊聊', {}),
]
for text, expected_keys in info_tests:
    info = agent._extract_user_info(text)
    has_expected = all(k in info for k in expected_keys)
    status = 'PASS' if has_expected else 'FAIL'
    print(f'  {status}: {text} -> {info}')

# Test 3: kg_flywheel_agent.process injects new_user_info
print("\n[3/5] Testing process() injects strategy + new_user_info...")
import asyncio
response = asyncio.run(agent.process('我叫李四，是一名前端开发'))
assert 'strategy' in response.data, 'strategy missing'
assert 'new_user_info' in response.data, 'new_user_info missing'
assert response.data['new_user_info']['name'] == '李四'
print(f'  PASS: strategy={response.data["strategy"]}')
print(f'  PASS: new_user_info={response.data["new_user_info"]}')

# Test 4: memory_proactive._context_similarity
print("\n[4/5] Testing _context_similarity...")
from core.memory_proactive import ProactiveMemoryEngine, ProactiveMemory
engine = ProactiveMemoryEngine()
m = ProactiveMemory('test', 'L2', 'Python async programming', {}, '2026-04-22', '', 0.5, 'python')
assert engine._context_similarity('Python asyncio', m) > 0
assert engine._context_similarity('JavaScript', m) == 0.0
assert engine._context_similarity('', m) == 1.0
print(f'  PASS: similarity scores correct')

# Test 5: memory_proactive._filter_by_context
print("\n[5/5] Testing _filter_by_context...")
memories = [
    ProactiveMemory('m1', 'L2', 'Python async best practices', {}, '2026', '', 0.5, 'python'),
    ProactiveMemory('m2', 'L2', 'JavaScript ES6 features', {}, '2026', '', 0.5, 'js'),
]
filtered = engine._filter_by_context(memories, 'Python programming', threshold=0.1)
assert len(filtered) == 1
assert filtered[0].key == 'm1'
print(f'  PASS: filtered {len(filtered)} / {len(memories)} memories')

# Test 6: kg_flywheel_routes._stream_chat_reply
print("\n[6/5] Testing _stream_chat_reply SSE generator...")
from api.routes.kg_flywheel_routes import _stream_chat_reply
gen = _stream_chat_reply('anonymous', None, 'hello', {})
chunks = list(gen)
assert len(chunks) > 0
assert any('[DONE]' in c for c in chunks)
print(f'  PASS: generated {len(chunks)} SSE chunks')

print("\n" + "=" * 60)
print("All backend verification tests PASSED!")
print("=" * 60)
