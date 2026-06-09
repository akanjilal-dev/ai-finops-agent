"""
tests/test_anomalies.py
=======================
The detectors are tested two ways: against tiny crafted series with known
outliers, and against the committed sample CSV (the idle GPU and the day-20
inference spike must both be found, and the healthy GPU must NOT be).
"""

import os

from finops.anomalies import (
    detect_idle_gpu,
    detect_inference_spikes,
    scan,
)
from finops.focus import load_focus, parse_focus

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_focus.csv")


def _gpu_rows(util, cost, days=5):
    return [
        {"ChargePeriodStart": f"2026-05-0{d + 1}", "ServiceName": "Amazon EC2",
         "ServiceCategory": "Compute", "ChargeCategory": "Usage",
         "BilledCost": str(cost), "EffectiveCost": str(cost),
         "ResourceId": "i-gpu", "ResourceType": "p4d.24xlarge",
         "ConsumedUnit": "GPU-Hours",
         "Tags": '{"utilization_pct": "%s"}' % util}
        for d in range(days)
    ]


def test_idle_gpu_detected_when_underutilised():
    records = list(parse_focus(_gpu_rows(util=2, cost=200)))
    findings = detect_idle_gpu(records)
    assert len(findings) == 1
    assert findings[0].kind == "IDLE_GPU"
    assert findings[0].impact_usd == 1000.0       # 200 * 5 days


def test_busy_gpu_not_flagged():
    records = list(parse_focus(_gpu_rows(util=80, cost=200)))
    assert detect_idle_gpu(records) == []


def test_inference_spike_detected():
    rows = [
        {"ChargePeriodStart": f"2026-05-{d + 1:02d}", "ServiceName": "Amazon Bedrock",
         "ServiceCategory": "AI and Machine Learning", "ChargeCategory": "Usage",
         "BilledCost": "50", "EffectiveCost": "50", "ResourceId": "bedrock"}
        for d in range(10)
    ]
    rows[5]["BilledCost"] = rows[5]["EffectiveCost"] = "500"   # the spike
    findings = detect_inference_spikes(list(parse_focus(rows)))
    assert len(findings) == 1
    assert findings[0].subject == "2026-05-06"


def test_steady_spend_has_no_spike():
    rows = [
        {"ChargePeriodStart": f"2026-05-{d + 1:02d}", "ServiceName": "Amazon Bedrock",
         "ServiceCategory": "AI and Machine Learning", "ChargeCategory": "Usage",
         "BilledCost": "50", "EffectiveCost": "50", "ResourceId": "bedrock"}
        for d in range(10)
    ]
    assert detect_inference_spikes(list(parse_focus(rows))) == []


def test_sample_csv_findings():
    records = load_focus(SAMPLE)
    findings = scan(records)
    kinds = {f.kind for f in findings}
    assert "IDLE_GPU" in kinds
    assert "INFERENCE_SPIKE" in kinds
    # the idle p4d is the subject of the idle finding; the healthy g5 never is
    idle = [f for f in findings if f.kind == "IDLE_GPU"]
    assert any("i-0idlep4dgpu01" in f.subject for f in idle)
    assert not any("i-0activeg5gpu1" in f.subject for f in idle)
    # the inference spike lands on 2026-05-20
    spikes = [f for f in findings if f.kind == "INFERENCE_SPIKE"]
    assert any(f.subject == "2026-05-20" for f in spikes)
