"""Bundled sample content mirroring the phnews Supabase shape.

Used as a fallback so the pipeline runs end-to-end offline (no Supabase), and as
fixtures for tests. Shapes match public.topics / public.angles /
public.source_examples columns.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


def sample_inputs(region: str = "ph", run_date: str = "2026-05-30"
                  ) -> Tuple[List[Dict], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    topics: List[Dict] = [
        {
            "id": "t-fuel-001", "region": region, "run_date": run_date,
            "name": "Philippine fuel price change this week",
            "name_zh": "本周菲律宾油价变动",
            "narrative": "Oil firms signal another adjustment as global crude swings.",
            "narrative_zh": "随着国际原油波动，油企暗示新一轮调整。",
            "topic_type": "economy", "density": 6, "bettable": True,
            "disposition": "top", "prob": 55,
            "R": 2, "S": 2, "T": 2, "U": 2, "H": 2,
            "suggested_question": "Will pump prices rise next week?",
            "suggested_question_zh": "下周油价会上涨吗？",
        },
        {
            "id": "t-bsp-002", "region": region, "run_date": run_date,
            "name": "BSP interest rate decision",
            "name_zh": "央行利率决议",
            "narrative": "The central bank weighs a hold versus a cut amid easing inflation.",
            "narrative_zh": "通胀放缓之际，央行在维持与降息之间权衡。",
            "topic_type": "economy", "density": 4, "bettable": True,
            "disposition": "candidate", "prob": 48,
            "R": 2, "S": 2, "T": 1, "U": 2, "H": 1,
            "suggested_question": "Will the BSP cut rates this month?",
            "suggested_question_zh": "本月央行会降息吗？",
        },
        {
            "id": "t-typhoon-003", "region": region, "run_date": run_date,
            "name": "Typhoon season landfall outlook",
            "name_zh": "台风季登陆前景",
            "narrative": "PAGASA tracks a developing low that may intensify.",
            "narrative_zh": "气象局正在追踪一个可能增强的低压。",
            "topic_type": "disaster", "density": 5, "bettable": True,
            "disposition": "top", "prob": 40,
            "R": 2, "S": 2, "T": 2, "U": 1, "H": 2,
            "suggested_question": "Will a typhoon make landfall this week?",
            "suggested_question_zh": "本周会有台风登陆吗？",
        },
        # Should be filtered out by guardrails (election/sensitive).
        {
            "id": "t-impeach-004", "region": region, "run_date": run_date,
            "name": "VP impeachment vote outlook",
            "name_zh": "副总统弹劾投票前景",
            "narrative": "The Senate debates whether to proceed to trial.",
            "narrative_zh": "参议院辩论是否进入审判程序。",
            "topic_type": "politics", "density": 8, "bettable": True,
            "disposition": "top", "prob": 50,
            "suggested_question": "Will the impeachment proceed?",
        },
        # Should be filtered out: not bettable.
        {
            "id": "t-celeb-005", "region": region, "run_date": run_date,
            "name": "Celebrity breakup rumor", "topic_type": "social",
            "density": 9, "bettable": False, "disposition": "drop",
        },
    ]
    angles: Dict[str, List[Dict]] = {
        "t-fuel-001": [
            {"id": "a-fuel-s", "topic_id": "t-fuel-001",
             "angle_type": "serious_candidate", "position": 0, "is_primary": True,
             "question_en": "Will pump prices rise next week?",
             "question_zh": "下周油价会上涨吗？"},
            {"id": "a-fuel-r", "topic_id": "t-fuel-001", "angle_type": "reddit",
             "position": 0, "is_primary": False,
             "question_en": "Will commuters notice before payday?",
             "question_zh": "通勤族会在发薪日前察觉吗？"},
        ],
        "t-bsp-002": [
            {"id": "a-bsp-s", "topic_id": "t-bsp-002",
             "angle_type": "serious_candidate", "position": 0, "is_primary": True,
             "question_en": "Will the BSP cut rates this month?",
             "question_zh": "本月央行会降息吗？"},
        ],
        "t-typhoon-003": [
            {"id": "a-typhoon-s", "topic_id": "t-typhoon-003",
             "angle_type": "serious_candidate", "position": 0, "is_primary": True,
             "question_en": "Will a typhoon make landfall this week?",
             "question_zh": "本周会有台风登陆吗？"},
        ],
    }
    source_examples: Dict[str, List[Dict]] = {
        "t-fuel-001": [
            {"id": "se-fuel-1", "topic_id": "t-fuel-001", "position": 0,
             "title_en": "Oil firms hint at price hike next week",
             "title_zh": "油企暗示下周涨价", "rank_score": 0.9,
             "link": "https://example.com/fuel"},
        ],
        "t-bsp-002": [
            {"id": "se-bsp-1", "topic_id": "t-bsp-002", "position": 0,
             "title_en": "Inflation eases, fueling rate-cut bets",
             "title_zh": "通胀放缓，降息预期升温", "rank_score": 0.8,
             "link": "https://example.com/bsp"},
        ],
    }
    return topics, angles, source_examples
