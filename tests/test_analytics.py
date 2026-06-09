"""
tests/test_analytics.py
=======================
Analytics are pure arithmetic, so they're tested against a tiny hand-built
dataset with known answers -- no dependence on the larger sample CSV.
"""

import pytest

from finops.analytics import (
    cost_by,
    cost_per_outcome,
    daily_cost,
    filter_ai,
    top_resources,
    total_cost,
)
from finops.focus import parse_focus

ROWS = [
    {"ChargePeriodStart": "2026-05-01", "ServiceName": "Amazon Bedrock",
     "ServiceCategory": "AI and Machine Learning", "ChargeCategory": "Usage",
     "BilledCost": "100", "EffectiveCost": "80", "ResourceId": "bedrock",
     "ConsumedQuantity": "40000", "ConsumedUnit": "Inferences",
     "RegionId": "us-east-1", "Tags": '{"team": "ml"}'},
    {"ChargePeriodStart": "2026-05-01", "ServiceName": "Amazon EC2",
     "ServiceCategory": "Compute", "ChargeCategory": "Usage",
     "BilledCost": "60", "EffectiveCost": "60", "ResourceId": "ec2",
     "ConsumedQuantity": "24", "ConsumedUnit": "GPU-Hours",
     "RegionId": "us-west-2", "Tags": '{"team": "infra"}'},
    {"ChargePeriodStart": "2026-05-02", "ServiceName": "Amazon Bedrock",
     "ServiceCategory": "AI and Machine Learning", "ChargeCategory": "Usage",
     "BilledCost": "20", "EffectiveCost": "20", "ResourceId": "bedrock",
     "ConsumedQuantity": "10000", "ConsumedUnit": "Inferences",
     "RegionId": "us-east-1", "Tags": '{"team": "ml"}'},
]


@pytest.fixture
def records():
    return list(parse_focus(ROWS))


def test_total_uses_effective_cost_by_default(records):
    assert total_cost(records) == 160.0          # 80 + 60 + 20
    assert total_cost(records, metric="BilledCost") == 180.0


def test_filter_ai(records):
    ai = filter_ai(records)
    assert len(ai) == 2
    assert total_cost(ai) == 100.0               # 80 + 20


def test_cost_by_service(records):
    by_service = cost_by(records, "service")
    assert by_service["Amazon Bedrock"] == 100.0
    assert by_service["Amazon EC2"] == 60.0
    # ordered high to low
    assert list(by_service) == ["Amazon Bedrock", "Amazon EC2"]


def test_cost_by_tag(records):
    by_team = cost_by(records, "tag:team")
    assert by_team == {"ml": 100.0, "infra": 60.0}


def test_daily_cost_is_chronological(records):
    daily = daily_cost(records)
    assert list(daily) == ["2026-05-01", "2026-05-02"]
    assert daily["2026-05-01"] == 140.0          # 80 + 60
    assert daily["2026-05-02"] == 20.0


def test_top_resources(records):
    top = top_resources(records, n=1)
    assert top == [("bedrock", 100.0)]


def test_cost_per_outcome(records):
    cpo = cost_per_outcome(records)
    assert cpo["outcomes"] == 50000              # only Inferences count
    assert cpo["cost"] == 100.0                  # 80 + 20
    assert cpo["cost_per_1k_outcomes"] == pytest.approx(2.0)  # $100 / 50k * 1000
