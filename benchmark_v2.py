#!/usr/bin/env python3
"""
MUSE V0.1 — Benchmark Pipeline Stabilization
5 runs · JSON validation · Raw logging · No interpretation
"""

import json
import openai
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# ========== CONFIG ==========
CULTURES_PATH = Path("cultures")
RESULTS_PATH = Path("results/raw")
FAILED_PATH = Path("results/failed_cases")
PROCESSED_PATH = Path("results/processed")

CULTURES = ["senegal_traditional_1800", "japan_modern_2000"]
SEEDS = [1001, 1002, 1003, 1004, 1005]
TEMPERATURE = 0.5

REQUIRED_FIELDS = [
    "fusion_name",
    "preserved_invariants",
    "identity_check",
    "physical_constraints_check",
    "silhouette",
    "materials"
]

PROMPT_TEMPLATE = """
You are MUSE, a multicultural fashion intelligence system.

Generate a fashion concept that fuses:
- Culture A: {culture_a}
- Culture B: {culture_b}

CRITICAL RULES:
1. Preserve core invariants of BOTH cultures
2. If identity failure condition triggers → identity_check.pass = false
3. If forbidden transformation triggered → identity_check.pass = false
4. Output must be physically plausible

OUTPUT FORMAT (VALID JSON ONLY, NO EXTRA TEXT):
{{
  "fusion_name": "string",
  "fusion_mood": "string",
  "preserved_invariants": {{
    "culture_a": ["invariant1", "invariant2"],
    "culture_b": ["invariant1", "invariant2"]
  }},
  "compromises": ["compromise1", "compromise2"],
  "silhouette": "string",
  "materials": ["string"],
  "colors": ["string"],
  "movement_logic": "string",
  "construction_logic": "string",
  "identity_check": {{
    "pass": true,
    "failure_reason": null
  }},
  "physical_constraints_check": {{
    "pass": true,
    "violations": []
  }}
}}

Use these culture definitions:

CULTURE A — {culture_a}:
{json_a}

CULTURE B — {culture_b}:
{json_b}
"""

def load_culture(culture_id: str) -> Dict:
    with open(CULTURES_PATH / f"{culture_id}.json", "r") as f:
        return json.load(f)

def validate_output(output: Dict, culture_a: str, culture_b: str) -> Dict[str, Any]:

    errors = []

    for field in REQUIRED_FIELDS:
        if field not in output:
            errors.append(f"Missing required field: {field}")

    if "preserved_invariants" in output:
        inv = output["preserved_invariants"]
        if culture_a not in inv:
            errors.append(f"Missing {culture_a} in preserved_invariants")
        if culture_b not in inv:
            errors.append(f"Missing {culture_b} in preserved_invariants")

    if "identity_check" in output:
        if "pass" not in output["identity_check"]:
            errors.append("identity_check missing 'pass' field")

    if "physical_constraints_check" in output:
        if "pass" not in output["physical_constraints_check"]:
            errors.append("physical_constraints_check missing 'pass' field")

    is_valid = len(errors) == 0

    return {
        "valid": is_valid,
        "errors": errors,
        "output": output if is_valid else None
    }

def run_experiment(culture_a: str, culture_b: str, seed: int) -> Optional[Dict]:

    json_a = json.dumps(load_culture(culture_a), indent=2)
    json_b = json.dumps(load_culture(culture_b), indent=2)

    prompt = PROMPT_TEMPLATE.format(
        culture_a=culture_a,
        culture_b=culture_b,
        json_a=json_a,
        json_b=json_b
    )

    for attempt in range(2):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=TEMPERATURE,
                seed=seed
            )

            raw_output = response.choices[0].message.content

            parsed = json.loads(raw_output)

            validation = validate_output(parsed, culture_a, culture_b)

            if validation["valid"]:
                return {
                    "culture_a": culture_a,
                    "culture_b": culture_b,
                    "seed": seed,
                    "temperature": TEMPERATURE,
                    "attempt": attempt + 1,
                    "timestamp": datetime.utcnow().isoformat(),
                    "raw_output": raw_output,
                    "output": parsed,
                    "validation": validation
                }
            else:
                failure = {
                    "type": "validation_failed",
                    "culture_a": culture_a,
                    "culture_b": culture_b,
                    "seed": seed,
                    "attempt": attempt + 1,
                    "errors": validation["errors"],
                    "raw_output": raw_output,
                    "timestamp": datetime.utcnow().isoformat()
                }

                with open(FAILED_PATH / f"validation_fail_{datetime.utcnow().timestamp()}.json", "w") as f:
                    json.dump(failure, f, indent=2)

        except json.JSONDecodeError as e:
            failure = {
                "type": "json_decode_error",
                "culture_a": culture_a,
                "culture_b": culture_b,
                "seed": seed,
                "attempt": attempt + 1,
                "error": str(e),
                "raw_output": raw_output if 'raw_output' in locals() else None,
                "timestamp": datetime.utcnow().isoformat()
            }

            with open(FAILED_PATH / f"json_error_{datetime.utcnow().timestamp()}.json", "w") as f:
                json.dump(failure, f, indent=2)

        except Exception as e:
            failure = {
                "type": "general_error",
                "culture_a": culture_a,
                "culture_b": culture_b,
                "seed": seed,
                "attempt": attempt + 1,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

            with open(FAILED_PATH / f"general_error_{datetime.utcnow().timestamp()}.json", "w") as f:
                json.dump(failure, f, indent=2)

    return None

def run_benchmark():

    RESULTS_PATH.mkdir(parents=True, exist_ok=True)
    FAILED_PATH.mkdir(parents=True, exist_ok=True)
    PROCESSED_PATH.mkdir(parents=True, exist_ok=True)

    successful_runs = []

    for culture_a, culture_b in [
        (CULTURES[0], CULTURES[1]),
        (CULTURES[1], CULTURES[0])
    ]:

        for seed in SEEDS:

            print(f"▶ Running: {culture_a} → {culture_b} | seed={seed}")

            result = run_experiment(culture_a, culture_b, seed)

            if result:
                successful_runs.append(result)

                filename = f"run_{culture_a}_{culture_b}_seed{seed}_{datetime.utcnow().timestamp()}.json"

                with open(RESULTS_PATH / filename, "w") as f:
                    json.dump(result, f, indent=2)

                print(f"  ✅ SUCCESS (attempt {result['attempt']})")

            else:
                print(f"  ❌ FAILED after retries")

    report = {
        "total_attempted": len(SEEDS) * 2,
        "successful": len(successful_runs),
        "failed": (len(SEEDS) * 2) - len(successful_runs),
        "success_rate": len(successful_runs) / (len(SEEDS) * 2) if SEEDS else 0,
        "cultures": CULTURES,
        "seeds": SEEDS,
        "temperature": TEMPERATURE,
        "timestamp": datetime.utcnow().isoformat()
    }

    with open(PROCESSED_PATH / "pipeline_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 50)
    print("PIPELINE STABILIZATION REPORT")
    print(json.dumps(report, indent=2))
    print("=" * 50)

    print("\n✅ DO NOT INTERPRET RESULTS YET")
    print("→ Check failed_cases/ for errors")
    print("→ Fix pipeline issues before adding complexity")

if __name__ == "__main__":
    run_benchmark()
