# Runtime smoke checks

Record only behavior observed in a real agent runtime. Installation, unit tests,
or a plausible answer are not runtime evidence.

## Evidence

- `D`: the runtime discovers the intended skill copy
- `E`: explicit `$watchlist-md` invocation is observable
- `B`: add, review, and transition cases produce the expected file behavior
- `R`: positive watchlist intent triggers and a generic reminder does not

Use `pass`, `fail`, `blocked`, or `pending`. Mark overall pass only when all four
codes use the same runtime version, model/mode, OS, configuration, and source
revision.

## Current evidence

| Runtime | D/E/B/R | Runtime/model/OS/config | Source revision | Overall | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Codex CLI 0.147.0 | pass/pass/pass/pass | `gpt-5.6-sol`; native Windows; ephemeral, user config and rules ignored, automatic approval review; unrelated app/browser/computer-use/image/multi-agent/hook features disabled | Runtime bundle SHA-256 `60b942a7c8ed4a7f3298c7e8164d50edc82a131a362a5de8a9452b850c85b248` | pending | 2026-08-14 | A sandboxed local core run covered discovery, explicit invocation, explicit and implicit private add, full read-only review, user-reported completion, duplicate-ID stop, unsupported-schema stop, and both generic negative-routing cases. Changed files passed the repository validator; the review file's Git blob stayed unchanged; stop cases left files and Git metadata unchanged. No sandbox bypass was used. |

The four evidence codes passed for that exact core run. Overall remains pending
because the other cases in `evals/smoke_cases.json` were not run; this row does
not claim full-corpus coverage.

The bundle digest is SHA-256 over the runtime files in ordinal relative-path
order, appending each UTF-8 relative path, a NUL byte, the raw file bytes, and a
final NUL byte.

Deterministic unit and CLI tests do not change this row. They validate the file
interface, not skill discovery, invocation, routing, or agent edits.

## Historical observation

An earlier version of this document recorded all four codes as passing on
2026-08-13 for `8c6e1cff810eaacc3425e03b10cd93bdbb2b6572`. That object is not available in
the current repository and was described as a local disposable snapshot rather
than a published commit. It is therefore a non-reproducible historical note and
does not support the current row.

## Procedure

1. Install an exact commit in a disposable workspace. For an uncommitted change,
   copy the runtime bundle and record a deterministic content digest.
2. Verify discovery and explicit invocation.
3. Create each selected case's declared `setup`, then run its prompt in a fresh
   workspace.
4. Compare observable files and routing with each case's `observe` list.
5. Use a disposable local folder when the runtime sandbox and approval boundary
   remain enforced. If a case needs a sandbox bypass, move that case to an
   OS-isolated container or VM instead of relying on folder deletion.
6. Record the executed case IDs and scope. Run every declared case before making
   a full-corpus claim.
7. Record a compact result here. Do not store transcripts, screenshots, raw
   private data, or credentials.

Add a runtime row only after someone runs this procedure. A documented skill path
without observed behavior is not a support claim.
