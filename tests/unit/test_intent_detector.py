# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path

from src.intent_detector.intent_detector import IntentDetector
from src.utils.action_intents import (
    INTENT_FILE_COPY,
    INTENT_FILE_DELETE,
    INTENT_FILE_MOVE,
)
from src.utils.confirmation_response import INTENT_AGREE, INTENT_DISAGREE
from src.utils.control_intents import (
    INTENT_BYE,
    INTENT_CAPABILITY,
    INTENT_DEFINITION,
    INTENT_EMOTIVE,
    INTENT_FEEDBACK,
    INTENT_PERSONAL_Q,
    INTENT_SMALLTALK,
    INTENT_TIME,
    INTENT_WEATHER,
)


class _FakeTaskManager:
    def __init__(self):
        self.active_tasks = {}

    def get_session_id(self, context=None):
        return (context or {}).get("session_id", "default_session")


class _FakeMorphAnalyzer:
    def analyze(self, context):
        text = context.get("original_text", "")
        context.setdefault("analysis", {})
        context["analysis"]["tokens"] = [{"base": text, "surface": text, "pos": "名詞"}]
        return context


class _FakeVectorEngine:
    _GROUP_BY_TEXT = {
        "そのファイルを削除して": "delete",
        "それを消して": "delete",
        "破棄": "delete",
        "これ削除して": "delete",
        "消しちゃって": "delete",
        "複製": "copy",
        "写し": "copy",
        "コピーして": "copy",
        "コピーを作って": "copy",
        "移して": "move",
        "場所変更": "move",
        "移動して": "move",
        "どこかに移して": "move",
        "OK": "agree",
        "はい": "agree",
        "はい、お願いします": "agree",
        "了解": "agree",
        "違います": "disagree",
        "ノー": "disagree",
        "いいえ": "disagree",
        "キャンセル": "disagree",
        "時間": "time",
        "時計": "time",
        "今何時？": "time",
        "時間教えて": "time",
        "こんにちは": "greeting",
        "バイバイ": "bye",
        "調子はどう？": "personal_q",
        "今日の天気は？": "weather",
        "何ができる？": "capability",
        "AIとは何？": "definition",
        "疲れたな": "emotive",
        "雑談しよう": "smalltalk",
        "ありがとう": "feedback",
    }

    def get_sentence_vector(self, words):
        if not words:
            return None
        return self._GROUP_BY_TEXT.get(words[0])

    def vector_similarity(self, v1, v2):
        if not v1 or not v2:
            return 0.0
        return 0.92 if v1 == v2 else 0.18


class TestIntentDetector(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.corpus_path = Path(self.temp_dir.name) / "intent_corpus.json"
        self.corpus_path.write_text(
            json.dumps(
                {
                    "intents": [
                        {"name": INTENT_FILE_DELETE, "examples": ["そのファイルを削除して", "それを消して", "破棄"]},
                        {"name": INTENT_FILE_COPY, "examples": ["複製", "写し", "コピーして"]},
                        {"name": INTENT_FILE_MOVE, "examples": ["移して", "場所変更", "移動して"]},
                        {"name": INTENT_AGREE, "examples": ["OK", "はい", "はい、お願いします"]},
                        {"name": INTENT_DISAGREE, "examples": ["違います", "ノー", "いいえ"]},
                        {"name": INTENT_TIME, "examples": ["時間", "時計", "今何時？"]},
                        {"name": "GREETING", "examples": ["こんにちは"]},
                        {"name": INTENT_BYE, "examples": ["バイバイ", "またね"]},
                        {"name": INTENT_PERSONAL_Q, "examples": ["元気ですか", "調子はどう？"]},
                        {"name": INTENT_WEATHER, "examples": ["今日の天気は？", "天気を教えて"]},
                        {"name": INTENT_CAPABILITY, "examples": ["何ができる？", "できることを教えて"]},
                        {"name": INTENT_DEFINITION, "examples": ["AIとは何？", "クラスとは何？"]},
                        {"name": INTENT_EMOTIVE, "examples": ["疲れたな", "へとへとです"]},
                        {"name": INTENT_SMALLTALK, "examples": ["雑談しよう", "最近どう？"]},
                        {"name": INTENT_FEEDBACK, "examples": ["ありがとう", "助かったよ"]},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.task_manager = _FakeTaskManager()
        self.detector = IntentDetector(self.task_manager, corpus_path=str(self.corpus_path))
        self.detector.set_vector_engine(_FakeVectorEngine())
        self.detector.prepare_corpus_vectors(_FakeMorphAnalyzer())

    def _detect(self, text, task=None, session_id="default_session"):
        context = {
            "original_text": text,
            "session_id": session_id,
            "analysis": {"tokens": [{"base": text, "surface": text, "pos": "名詞"}]},
            "pipeline_history": [],
        }
        if task is not None:
            context["task"] = task
        return self.detector.detect(context)

    def test_detect_maps_delete_synonym_to_file_delete(self):
        result = self._detect("これ削除して")
        self.assertEqual(result["analysis"]["intent"], INTENT_FILE_DELETE)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_copy_synonym_to_file_copy(self):
        result = self._detect("コピーを作って")
        self.assertEqual(result["analysis"]["intent"], INTENT_FILE_COPY)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_move_synonym_to_file_move(self):
        result = self._detect("どこかに移して")
        self.assertEqual(result["analysis"]["intent"], INTENT_FILE_MOVE)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_boosts_agree_during_approval_clarification(self):
        task = {
            "name": "CMD_RUN",
            "state": "READY_FOR_EXECUTION",
            "clarification_needed": True,
            "clarification_type": "APPROVAL",
        }
        self.task_manager.active_tasks["default_session"] = task
        result = self._detect("了解", task=task)
        self.assertEqual(result["analysis"]["intent"], INTENT_AGREE)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_boosts_disagree_during_approval_clarification(self):
        task = {
            "name": "CMD_RUN",
            "state": "READY_FOR_EXECUTION",
            "clarification_needed": True,
            "clarification_type": "APPROVAL",
        }
        self.task_manager.active_tasks["default_session"] = task
        result = self._detect("キャンセル", task=task)
        self.assertEqual(result["analysis"]["intent"], INTENT_DISAGREE)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_time_variation_to_time_intent(self):
        result = self._detect("時間教えて")
        self.assertEqual(result["analysis"]["intent"], INTENT_TIME)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_bye_variation_to_bye_intent(self):
        result = self._detect("バイバイ")
        self.assertEqual(result["analysis"]["intent"], INTENT_BYE)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_personal_question_variation_to_personal_q_intent(self):
        result = self._detect("調子はどう？")
        self.assertEqual(result["analysis"]["intent"], INTENT_PERSONAL_Q)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_weather_variation_to_weather_intent(self):
        result = self._detect("今日の天気は？")
        self.assertEqual(result["analysis"]["intent"], INTENT_WEATHER)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_capability_variation_to_capability_intent(self):
        result = self._detect("何ができる？")
        self.assertEqual(result["analysis"]["intent"], INTENT_CAPABILITY)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_definition_variation_to_definition_intent(self):
        result = self._detect("AIとは何？")
        self.assertEqual(result["analysis"]["intent"], INTENT_DEFINITION)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_emotive_variation_to_emotive_intent(self):
        result = self._detect("疲れたな")
        self.assertEqual(result["analysis"]["intent"], INTENT_EMOTIVE)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_smalltalk_variation_to_smalltalk_intent(self):
        result = self._detect("雑談しよう")
        self.assertEqual(result["analysis"]["intent"], INTENT_SMALLTALK)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)

    def test_detect_maps_feedback_variation_to_feedback_intent(self):
        result = self._detect("ありがとう")
        self.assertEqual(result["analysis"]["intent"], INTENT_FEEDBACK)
        self.assertGreater(result["analysis"]["intent_confidence"], 0.60)
