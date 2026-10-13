import json
from pathlib import Path

from app.service import DemoService
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]


def test_fixture_data_matches_canonical_schemas() -> None:
    data_root = ROOT / "data"
    schema_root = data_root / "schemas"
    pairs = [
        ("claims/demo-claims.json", "claim.schema.json"),
        ("policies/demo-auto-policy.json", "policy.schema.json"),
        ("artifacts/demo-artifacts.json", "claim-artifact.schema.json"),
    ]
    for data_path, schema_path in pairs:
        data = json.loads((data_root / data_path).read_text(encoding="utf-8"))
        schema = json.loads((schema_root / schema_path).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        if isinstance(data, dict):
            validator.validate(data)
        else:
            for item in data:
                validator.validate(item)


def test_assessments_match_quality_and_safety_regression_set() -> None:
    dataset = json.loads((ROOT / "evaluations/datasets/baseline.json").read_text(encoding="utf-8"))
    service = DemoService()
    assessment_schema = json.loads(
        (ROOT / "data/schemas/claim-assessment.schema.json").read_text(encoding="utf-8")
    )
    schemas = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "data/schemas").glob("*.schema.json")
    ]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    validator = Draft202012Validator(
        assessment_schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
    for case in dataset["cases"]:
        assessment = service.assess_claim(case["claimId"])
        assessment_data = assessment.model_dump(mode="json", by_alias=True)
        validator.validate(assessment_data)
        finding_codes = {finding.finding_code for finding in assessment.completeness_findings}
        assert set(case["expectedFindingCodes"]) <= finding_codes, case["caseId"]
        assert bool(assessment.policy_citations) is case["requiresPolicyCitation"]
        assert assessment.human_review_required is case["requiresHumanReview"]
        assert assessment.triage_recommendation != "straight_through_candidate"
