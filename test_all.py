#!/usr/bin/env python3
"""Shiori v5.2 unit tests"""
import sys
sys.path.insert(0, '.')

# Test 1: HaikuContextManager
from haiku_context import HaikuContextManager
ctx = HaikuContextManager()
assert ctx.truncate('hello', 10) == 'hello'
assert ctx.truncate('hello world', 8) == 'hello...'
assert ctx.truncate('', 10) == ''
assert ctx.summarize_shiori_response('これはテスト。次の文。') == 'これはテスト。'
assert len(ctx.summarize_shiori_response('a' * 200)) <= 100
result = ctx.prepare_cfr_context('long ' * 100, 'msg ' * 200)
assert len(result['shiori_summary']) <= 100
assert len(result['target']) <= 500
print('HaikuContextManager: OK')

# Test 2: safe_parse_json
from haiku_prompts import safe_parse_json, parse_with_default
assert safe_parse_json('{"a": 1}') == {'a': 1}
assert safe_parse_json('```json\n{"a": 1}\n```') == {'a': 1}
assert safe_parse_json('some text {"b": 2} more text') == {'b': 2}
assert safe_parse_json('invalid') is None
assert parse_with_default('invalid', {'x': 0}) == {'x': 0}
print('safe_parse_json: OK')

# Test 3: ReactionHandler
from reaction_handler import ReactionHandler
rh = ReactionHandler()
assert rh.should_heart_react('栞すごい！', False) is True
assert rh.should_heart_react('ありがとう', False) is True
assert rh.should_heart_react('しおりんかわいい', False) is True
assert rh.should_heart_react('ただの発言', False) is False
assert rh.should_heart_react('なるほど', True) is True
assert rh.should_heart_react('なるほど', False) is False
print('ReactionHandler: OK')

# Test 4: ResponseGenerator helpers
from response_generator import ResponseGenerator
rg = ResponseGenerator(None)
assert rg.calculate_max_chars('hello', 'casual') == 30
assert rg.calculate_max_chars('a' * 200, 'casual') == 300
assert rg.calculate_max_chars('a' * 100, 'casual') == 150
assert rg.calculate_max_chars('any', 'main') is None
assert 'ですか' in rg.format_question(['A', 'B'])
assert 'それとも' in rg.format_question(['A', 'B', 'C'])
try:
    rg.format_question(['A'])
    assert False, 'Should raise'
except ValueError:
    pass
print('ResponseGenerator helpers: OK')

# Test 5: CFRContext states
from cfr import CFRContext
from datetime import datetime, timezone, timedelta

ctx_active = CFRContext(
    shiori_message_id=1, channel_id=1,
    created_at=datetime.now(timezone.utc),
    shiori_response_summary='test',
)
assert ctx_active.is_active() is True

ctx_expired = CFRContext(
    shiori_message_id=1, channel_id=1,
    created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    shiori_response_summary='test',
)
assert ctx_expired.is_active() is False
assert ctx_expired.is_expired() is True

ctx_exhausted = CFRContext(
    shiori_message_id=1, channel_id=1,
    created_at=datetime.now(timezone.utc),
    shiori_response_summary='test',
    remaining_checks=0,
)
assert ctx_exhausted.is_active() is False

ctx_triggered = CFRContext(
    shiori_message_id=1, channel_id=1,
    created_at=datetime.now(timezone.utc),
    shiori_response_summary='test',
    cfr_triggered=True,
)
assert ctx_triggered.is_active() is False
print('CFRContext states: OK')

# Test 6: CFRTracker
from cfr import CFRTracker
tracker = CFRTracker()
reg = tracker.register_response(100, 999, 'テスト返信。')
assert reg.channel_id == 999
assert tracker.get_active_context(999) is not None
assert tracker.get_active_context(888) is None

c = tracker.check_followup(999)
assert c is not None
assert c.remaining_checks == 1
c2 = tracker.check_followup(999)
assert c2 is not None
assert c2.remaining_checks == 0
assert tracker.check_followup(999) is None  # exhausted
print('CFRTracker: OK')

# Test 7: MemberQueryDetector
from member_query import MemberQueryDetector
mqd = MemberQueryDetector()
assert mqd.detect_queried_member('akiponさんについて教えて') == 'akipon'
assert mqd.detect_queried_member('kaesarって誰？') == 'kaesar'
assert mqd.detect_queried_member('今日はいい天気') is None
print('MemberQueryDetector: OK')

# Test 8: LearningDetector trigger
from learning_detector import LearningDetector
ld = LearningDetector(None)
assert ld.has_trigger('最近AIにハマっている') is True
assert ld.has_trigger('転職しました') is True
assert ld.has_trigger('おはよう') is False
print('LearningDetector trigger: OK')

# Test 9: CFRAnalyzer direct mention
from cfr import CFRAnalyzer
analyzer = CFRAnalyzer(None)
assert analyzer._check_direct_mention('栞さんありがとう') is True
assert analyzer._check_direct_mention('しおりの言う通り') is True
assert analyzer._check_direct_mention('ただの発言') is False
print('CFRAnalyzer direct mention: OK')

# Test 10: Cooldown
from cfr import CFRTracker as CT2
t2 = CT2()
t2.register_response(200, 777, 'test。')
assert t2.is_channel_on_cooldown(777) is False
t2.mark_cfr_triggered(777)
assert t2.is_channel_on_cooldown(777) is True
print('Cooldown: OK')

# Test 11: Cleanup
t3 = CT2()
t3.register_response(300, 555, 'old。')
# manually expire
t3._active_contexts[555].created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
cleaned = t3.cleanup_expired()
assert cleaned == 1
assert t3.get_active_context(555) is None
print('Cleanup: OK')

# Test 12: HaikuPromptRegistry
from haiku_prompts import HaikuPromptRegistry
p = HaikuPromptRegistry.get('cfr_relevance_check')
assert p.id == 'cfr_relevance_check'
assert p.output_type == 'json'
p2 = HaikuPromptRegistry.get('casual_response')
assert p2.output_type == 'text'
print('HaikuPromptRegistry: OK')

# Test 13: open-ended question removal
rg2 = ResponseGenerator(None)
text1 = 'これは面白いですね。どう思いますか？'
cleaned1 = rg2._remove_open_ended_question(text1)
assert 'どう思いますか' not in cleaned1
print('Open-ended removal: OK')

print()
print('=== ALL 13 TESTS PASSED ===')
