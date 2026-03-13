# Contributing to DriftWatch

Thank you for your interest in contributing! DriftWatch is MIT licensed and welcomes contributions.

## Ways to Contribute

### 1. Add Test Prompts
The most valuable contribution is sharing prompt patterns that you've seen drift in production. Add them to `core/test_suite.py`:

```python
{
    "id": "your-prompt-id",
    "name": "Brief description",
    "prompt": "Your actual prompt text",
    "validators": ["json_valid", "length_stable"],  # see validator list below
    "category": "json | instruction | code | classification | extraction | safety | verbosity"
}
```

**Validator options:**
- `json_valid` — response must be parseable JSON
- `length_stable` — response length stays within 20% of baseline
- `exact_match` — response exactly matches baseline
- `contains_keywords` — response contains required terms
- `format_compliance` — response follows specified format

### 2. Report Drift Detections
Open an issue with:
- Model + provider
- Prompt type (JSON extraction, classification, etc.)
- What changed (format, verbosity, factual accuracy)
- DriftWatch score if available

Use the [LLM Drift Report template](.github/ISSUE_TEMPLATE/drift-report.md) (coming soon).

### 3. Improve the Detection Engine
The core detector is in `core/drift_detector.py`. Key areas:
- Semantic similarity algorithms (currently cosine similarity via TF-IDF)
- Format compliance validators
- Alert threshold tuning

### 4. Backend Improvements
FastAPI backend in `backend/`. Key files:
- `main.py` — API endpoints
- `scheduler.py` — APScheduler drift check jobs
- `alerts.py` — Slack/email alerting
- `drift_runner.py` — production drift execution

## Development Setup

```bash
git clone https://github.com/GenesisClawbot/llm-drift.git
cd llm-drift
pip install -r requirements.txt

# Core drift detector (no backend needed)
export ANTHROPIC_API_KEY=sk-ant-...
python3 core/drift_detector.py --run baseline
python3 core/drift_detector.py --run check

# Backend (full SaaS)
pip install -r requirements-backend.txt
cd backend && uvicorn main:app --reload --port 9001
```

## Pull Request Guidelines

- Keep PRs focused — one feature/fix per PR
- Update tests if changing detection logic
- Real drift data > synthetic examples
- Document new validators in this file

## Questions?

Open a [GitHub Discussion](https://github.com/GenesisClawbot/llm-drift/discussions) — we especially want to hear your LLM drift stories.
