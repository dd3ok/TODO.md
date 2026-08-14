# Contributing

Keep one source of truth for each behavior:

- agent workflow and schema: `.agents/skills/watchlist-md/SKILL.md`
- generated file skeleton: `.agents/skills/watchlist-md/assets/WATCHLIST.template.md`
- deterministic schema validation: `tools/validate_watchlist.py`
- manual runtime behavior cases: `evals/smoke_cases.json`

Update `.agents/skills/watchlist-md/agents/openai.yaml` when the skill's trigger
or example prompt changes. Update README and validation documentation when the
public interface changes.

Run:

```bash
python -B -m unittest discover -s evals -p 'test_*.py'
python -B tools/validate_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md
```

Use a real runtime smoke check for behavior claims; do not turn expected outputs
into claims that an agent was executed. Keep secrets, raw private content, and
credential-bearing URLs out of tests, issues, and pull requests.
