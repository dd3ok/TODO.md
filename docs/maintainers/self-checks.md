# Maintainer Self-Check Guide

Do not maintain a second prompt catalog in this document. The canonical semantic
contracts live in `evals/cases/*.json`; `evals/prompts.csv` and
`evals/self_checks.yaml` are deliberately checked mirrors for tabular and manual
review.

## Run The Deterministic Checks

```bash
python3 evals/check_semantic_cases.py
python3 -m unittest discover -s evals -p 'test_*.py'
```

`check_semantic_cases.py` does not call an LLM or the network. It checks case
shape, fixture validity, prompt/trigger parity across all three representations,
supported operations, lifecycle requirements, and the lightweight trigger
corpus.

## Add Or Change A Case

1. Add or update the authoritative JSON contract in `evals/cases/`.
2. Mirror the exact `id`, prompt, and trigger decision in `evals/prompts.csv` and
   `evals/self_checks.yaml`.
3. Extend the operation validator when introducing a new contract shape; unknown
   keys intentionally fail instead of being ignored.
4. Add a focused unit test for new linter behavior and run the commands above.

The current lifecycle corpus covers add, review, complete, snooze, block, reopen,
drop, delete, archive, permission, storage selection, secret refusal, collision,
and negative-trigger behavior. Inspect the JSON cases for exact prompts and
expected mutations rather than copying them here.

## Manual Runtime Checks

Deterministic contracts do not prove vendor runtime behavior. Use
`docs/runtime-smoke.md` for discovery, explicit invocation, behavior, and routing
evidence. Record only an actually executed runtime result and never add raw
transcripts, screenshots, or logs to the repository.
