#!/usr/bin/env python3
import json
from pathlib import Path

src = Path("results/v0.11.0/controller-prototype/offline-controller-profile-coverage.json")
out = Path("results/v0.11.0/controller-prototype/offline-controller-safety-checks.json")
order = {"PASS": 0, "WARN": 1, "FAIL": 2}

def worse(a, b):
	return b if order[b] > order[a] else a

data = json.loads(src.read_text())
case_results = []

for case in data["results"]:
	m = case["metrics"]
	status = "PASS"
	reasons = []
	if m["saturation_fraction"] > 0.50:
		status = worse(status, "FAIL")
		reasons.append("saturation_fraction > 0.50")
	if m["max_abs_error"] > 8.0:
		status = worse(status, "FAIL")
		reasons.append("max_abs_error > 8.0")
	if abs(m["final_error"]) > 2.0:
		status = worse(status, "FAIL")
		reasons.append("abs(final_error) > 2.0")
	if m["mean_abs_command_change"] > 12.0:
		status = worse(status, "FAIL")
		reasons.append("mean_abs_command_change > 12.0")
	if m["saturation_fraction"] > 0.20:
		status = worse(status, "WARN")
		reasons.append("saturation_fraction > 0.20")
	if m.get("anti_windup_freeze_fraction", 0.0) > 0.20:
		status = worse(status, "WARN")
		reasons.append("anti_windup_freeze_fraction > 0.20")
	if abs(m["mean_error"]) > 0.25:
		status = worse(status, "WARN")
		reasons.append("abs(mean_error) > 0.25")
	if m["mae"] > 0.50:
		status = worse(status, "WARN")
		reasons.append("mae > 0.50")
	if not reasons:
		reasons.append("no safety warnings or failures")
	case_results.append({
		"profile": case["profile"],
		"controller_case": case["controller_case"],
		"status": status,
		"reasons": reasons,
		"metrics": m
	})

counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
overall = "PASS"

for item in case_results:
	counts[item["status"]] += 1
	overall = worse(overall, item["status"])

payload = {
	"stage": "v0.11.0-throughput-controller-prototype",
	"check": "offline-controller-safety-checks",
	"source": str(src),
	"summary": {
		"overall_status": overall,
		"counts": counts
	},
	"case_results": case_results
}

out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"safety_json: {out}")
print(f"overall: {overall}")
print(f"counts: {counts}")
