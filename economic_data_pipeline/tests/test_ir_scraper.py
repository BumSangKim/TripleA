# tests/test_ir_scraper.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ir_scraper import COMPANY_CIKS, count_ai_bottleneck_keywords


def test_ai_bottleneck_ciks_include_requested_targets():
    for ticker in ["NVDA", "AMD", "MU", "AVGO", "SMCI", "DELL"]:
        assert ticker in COMPANY_CIKS


def test_count_ai_bottleneck_keywords():
    text = "HBM HBM3E CoWoS lead time backlog tight supply advanced packaging supply constrained allocation"
    counts = count_ai_bottleneck_keywords(text)
    assert counts["HBM"] == 1
    assert counts["HBM3E"] == 1
    assert counts["CoWoS"] == 1
    assert counts["lead time"] == 1
    assert counts["allocation"] == 1
    assert counts["supply constrained"] == 1
    assert counts["tight supply"] == 1
    assert counts["backlog"] == 1
    assert counts["advanced packaging"] == 1
