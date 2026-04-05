"""
knowledge_extractor.py — 算法知识提取服务
Algorithmically extracts knowledge candidates from group chat messages.
Ported from OlivOS Assassin's QA pair detection and keyword extraction.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from astrbot.api import logger

from ..storage.models import CandidateRecord, CandidateStatus

# ---------------------------------------------------------------------------
#  Text utility functions
# ---------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    r'\[CQ:face[^\]]*\]'
    r'|\[OP:face[^\]]*\]'
    r'|[\U00010000-\U0010ffff]'
    r'|[\u2600-\u27bf\u2300-\u23ff\ufe00-\ufe0f\u200d\u20e3\ufe0f]',
    re.UNICODE,
)

_QA_QUESTION_MARKERS = (
    '?', '？', '怎么', '如何', '为什么', '咋', '吗', '求',
    '不会', '打不开', '装不上', '进不去', '下不了', '有没有',
    '能不能', '是不是', '哪里', '什么', '谁', '多少',
)

_UNCERTAIN_MARKERS = (
    '不知道', '不清楚', '不太清楚', '不确定', '可能', '也许',
    '大概', '应该吧', '我忘了', '记不清', '你去看看', '你自己看',
    '搜一下', '自己试试', '不懂', '随便', '啊对对对', '好像是',
)


def _clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '').replace('\r', ' ').replace('\n', ' ')).strip()


def _looks_like_question(text: str) -> bool:
    cleaned = _clean_text(text).lower()
    if not cleaned:
        return False
    return any(marker in cleaned for marker in _QA_QUESTION_MARKERS)


def _looks_like_low_signal(text: str) -> bool:
    cleaned = _clean_text(text).lower()
    if not cleaned or len(cleaned) <= 3:
        return True
    if re.fullmatch(r'[哈啊哦嗯呃欸诶草6]+', cleaned):
        return True
    if re.fullmatch(r'[.。,，!！?？~～、\-_=+*/\\|\s]+', cleaned):
        return True
    return False


def _looks_like_uncertain(text: str) -> bool:
    cleaned = _clean_text(text).lower()
    if not cleaned:
        return True
    return any(m in cleaned for m in _UNCERTAIN_MARKERS)


def _has_sufficient_density(text: str) -> bool:
    """Check if text has sufficient information density."""
    cleaned = _clean_text(text)
    if len(cleaned) < 10:
        return False
    fragments = [f for f in re.split(r'[，。；、,.!?？!\s]+', cleaned) if _clean_text(f)]
    informative = [f for f in fragments if len(f) >= 2]
    return len(informative) >= 2 or len(cleaned) >= 18


def _extract_keywords(text: str, max_count: int = 6) -> List[str]:
    """Algorithmically extract keywords from text."""
    result: List[str] = []

    def _add(candidate: str) -> None:
        c = _clean_text(candidate)
        if c and len(c) >= 2 and len(c) <= 30 and c not in result:
            result.append(c)

    # English acronyms / identifiers
    for m in re.findall(r'\b[A-Z]{2,10}\b', text):
        _add(m)
    for m in re.findall(r'\b[A-Za-z][A-Za-z0-9._+-]{3,23}\b', text):
        _add(m)

    # Chinese phrase splitting
    clauses = re.split(r'[，。；、,.!?？!()\[\]【】/:：\s]+', text)
    for clause in clauses:
        if not re.search(r'[\u4e00-\u9fff]', clause):
            continue
        for piece in re.split(r'[和与及并]', clause):
            _add(piece)

    return result[:max_count]


# ---------------------------------------------------------------------------
#  Chat history buffer per group
# ---------------------------------------------------------------------------

@dataclass
class ChatEntry:
    user_id: str
    nickname: str
    message: str
    timestamp: float
    group_id: str


class KnowledgeExtractor:
    """
    Detects knowledge-worthy QA pairs from group chat via two pathways:

    1. **User-User QA** — buffers group messages; when a substantive answer
       follows a question from a different user, creates a candidate.
    2. **User-Bot QA** — when the bot answers a user's question and the
       response has sufficient density, creates a candidate.

    从群聊中通过两条路径检测有价值的问答对：
    1. 用户-用户 QA：缓存消息历史，当一条问题后面有不同用户的实质性回答时生成候选。
    2. 用户-Bot QA：当 Bot 回答了用户的提问且回复有足够信息密度时生成候选。
    """

    def __init__(
        self,
        *,
        history_size: int = 30,
        qa_max_gap_sec: float = 300,
        min_answer_len: int = 10,
        cooldown_sec: float = 300,
    ):
        self._history: Dict[str, deque] = {}  # group_id -> deque of ChatEntry
        self._history_size = history_size
        self._qa_max_gap = qa_max_gap_sec
        self._min_answer_len = min_answer_len
        self._cooldown_sec = cooldown_sec
        # Dedup: track recently created candidate hashes
        self._recent_candidates: Dict[str, float] = {}

    def _get_history(self, group_id: str) -> deque:
        if group_id not in self._history:
            self._history[group_id] = deque(maxlen=self._history_size)
        return self._history[group_id]

    # ------------------------------------------------------------------
    #  Pathway 1: User-User QA detection (buffer + backward search)
    # ------------------------------------------------------------------

    def process_message(
        self,
        group_id: str,
        user_id: str,
        nickname: str,
        message: str,
    ) -> Optional[CandidateRecord]:
        """
        Buffer a group message and check for user-user QA pairs.
        Returns a CandidateRecord if a valid QA pair is detected.
        """
        text = _clean_text(message)
        if not text:
            return None

        entry = ChatEntry(
            user_id=user_id,
            nickname=nickname,
            message=text,
            timestamp=time.time(),
            group_id=group_id,
        )
        history = self._get_history(group_id)
        history.append(entry)

        # Only check when the new message looks like a substantive answer
        if _looks_like_question(text):
            return None
        if _looks_like_low_signal(text):
            return None
        if _looks_like_uncertain(text):
            return None
        if len(text) < self._min_answer_len:
            return None
        if not _has_sufficient_density(text):
            return None

        # Look backward for a recent question from a different user
        question_entry = self._find_recent_question(history, entry)
        if question_entry is None:
            return None

        return self._build_candidate_from_entries(question_entry, entry, 'user_qa')

    # ------------------------------------------------------------------
    #  Pathway 2: User-Bot QA detection
    # ------------------------------------------------------------------

    def process_bot_qa(
        self,
        group_id: str,
        user_id: str,
        nickname: str,
        question: str,
        bot_answer: str,
    ) -> Optional[CandidateRecord]:
        """
        Check if a user-bot interaction forms a valid knowledge QA pair.
        Called from on_decorating_result with the user's message and
        the bot's generated response text.

        从 on_decorating_result 调用：用户的消息作为问题，
        Bot 的生成文本作为回答。
        """
        q_text = _clean_text(question)
        a_text = _clean_text(bot_answer)

        if not q_text or not a_text:
            return None
        if not _looks_like_question(q_text):
            return None
        if len(a_text) < self._min_answer_len:
            return None
        if not _has_sufficient_density(a_text):
            return None
        if _looks_like_uncertain(a_text):
            return None

        return self._build_candidate_record(
            q_text=q_text,
            a_text=a_text,
            asker_id=user_id,
            asker_name=nickname,
            answerer_id='bot',
            answerer_name='AstrBot',
            group_id=group_id,
            source_type='bot_qa',
            confidence=0.65,
        )

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _find_recent_question(
        self, history: deque, answer: ChatEntry
    ) -> Optional[ChatEntry]:
        """Search backward for a question from a different user."""
        for i in range(len(history) - 2, -1, -1):
            q = history[i]
            if q.user_id == answer.user_id:
                continue
            if answer.timestamp - q.timestamp > self._qa_max_gap:
                break
            if _looks_like_question(q.message):
                return q
        return None

    def _build_candidate_from_entries(
        self, question: ChatEntry, answer: ChatEntry, source_type: str
    ) -> Optional[CandidateRecord]:
        """Build a CandidateRecord from two ChatEntry objects."""
        return self._build_candidate_record(
            q_text=question.message,
            a_text=answer.message,
            asker_id=question.user_id,
            asker_name=question.nickname,
            answerer_id=answer.user_id,
            answerer_name=answer.nickname,
            group_id=question.group_id,
            source_type=source_type,
            confidence=0.5,
        )

    def _build_candidate_record(
        self,
        *,
        q_text: str,
        a_text: str,
        asker_id: str,
        asker_name: str,
        answerer_id: str,
        answerer_name: str,
        group_id: str,
        source_type: str,
        confidence: float,
    ) -> Optional[CandidateRecord]:
        """Dedup, extract keywords, and create a CandidateRecord."""
        fingerprint = hashlib.sha256(
            (_clean_text(q_text) + _clean_text(a_text)).encode('utf-8')
        ).hexdigest()

        now = time.time()
        if fingerprint in self._recent_candidates:
            if now - self._recent_candidates[fingerprint] < self._cooldown_sec:
                return None
        self._recent_candidates[fingerprint] = now

        # Prune old entries
        cutoff = now - self._cooldown_sec * 2
        self._recent_candidates = {
            k: v for k, v in self._recent_candidates.items() if v > cutoff
        }

        keywords = _extract_keywords(q_text + ' ' + a_text)
        if not keywords:
            return None

        summary = q_text[:80] + ' → ' + a_text[:120]

        return CandidateRecord(
            title=q_text[:100],
            type='faq_card',
            base_type='factual',
            schema_data={
                'question': q_text,
                'answer': a_text,
                'asker_id': asker_id,
                'asker_name': asker_name,
                'answerer_id': answerer_id,
                'answerer_name': answerer_name,
                'group_id': group_id,
            },
            raw_text=summary,
            keywords=keywords,
            confidence=confidence,
            status=CandidateStatus.NEW,
            source_plugin=f'auto_extractor_{source_type}',
            source_refs=[{
                'type': source_type,
                'group_id': group_id,
                'question_user': asker_id,
                'answer_user': answerer_id,
                'timestamp': now,
            }],
        )
