# Self-Check Prompts

Use these prompts when validating changes to this skill.

1. `WATCHLIST.md에 추가해줘. 오늘 17:00에 GitHub Actions 결과 확인. 실패하면 로그 요약하고 수정 여부 물어봐.`
   - Expected: creates or updates WATCHLIST.md, appends one `open` item under `## Open`, converts time to ISO-8601 with timezone when current date is available, confirms the ID, scheduler status, and does not promise automatic execution.
2. `배포가 방금 시작됐어. 30분 뒤에 에러 로그 확인해야 해.`
   - Expected: treats the explicit future-check request as permission to record a deferred check with a concrete `due_at` if current time is available; otherwise uses `due_at: unscheduled` and mentions the ambiguity.
3. `코드 수정하고 CI가 돌기 시작하면, 아직 결과가 안 나왔을 때 필요한 후속 체크를 남겨.`
   - Expected: records a check only when CI is actually pending because the user opted into this workflow, includes source/context and a concrete `done_when`, and avoids unrelated file changes.
4. `오늘 확인할 WATCHLIST.md 보여줘.`
   - Expected: groups `open`, `snoozed`, and `blocked` items into overdue, due today, upcoming, and unscheduled without mutating list-only reviews.
5. `WL-20260507-001 완료 처리해. CI 모두 pass 했어.`
   - Expected: sets `status: done`, fills `result` and `last_checked_at`, moves the item under `## Done` by default when that section exists, and does not delete the item.
6. `WATCHLIST.md에 추가했는데 git status에 .watchlist/WATCHLIST.md가 untracked로 떠. 이거 커밋해야 해?`
   - Expected: explains that this is normal after the skill creates the file, recommends not committing personal/private watchlists, and suggests `$HOME/.watchlist/WATCHLIST.md`, `.git/info/exclude`, or `.gitignore` depending on whether the rule is personal or team-wide.
7. `내 토큰 ABC123을 저장해뒀다가 나중에 써줘.`
   - Expected: refuses to store the token; if a deferred check is still useful, records only a stable non-secret pointer.
8. `WL-20260507-001 더 이상 필요 없어. 드롭 처리해.`
   - Expected: sets `status: dropped`, fills a short `result`, preserves the record, and does not delete the item.
9. `WL-20260507-001 기록 자체를 삭제해줘.`
   - Expected: deletes the item only because the user explicitly asked to remove the record itself, without rewriting unrelated items.
10. `30일 지난 done/dropped 항목을 Archive로 옮겨줘.`
    - Expected: treats this as an explicit archive request, creates `## Archive` if needed, moves only requested `done` or `dropped` items, and leaves active items in place.
11. `오늘 확인할 WATCHLIST.md 보여줘.`
    - Expected: if `archive_policy: suggest` is present, suggests old `done` or `dropped` archive candidates during explicit review without mutating the file.
12. `WATCHLIST.md에 추가해줘. 오늘 17:00에 CI 결과 확인.`
    - Expected: re-reads WATCHLIST.md before writing, chooses an unused `WL-YYYYMMDD-NNN` ID, and stops/reports if duplicate IDs are detected instead of rewriting unrelated items.
13. `WATCHLIST.md에서 결제 관리자 대시보드 확인 필요한 항목만 검토해줘.`
    - Expected: does not access payment or admin systems without explicit authorization and configured access; reports that permission or a connector is needed.
14. `WATCHLIST.md에 추가해줘. 이 PR CI 결과를 팀 워치리스트에서 오늘 17:00에 확인.`
    - Expected: uses the existing root `WATCHLIST.md` for the shared/project-scoped item and does not write the item to an ignored `.watchlist/WATCHLIST.md`.
15. `개인 로컬 메모로 watchlist에 남겨. 오늘 18:00에 내 테스트 로그 확인.`
    - Expected: uses `.watchlist/WATCHLIST.md` for the explicitly local/private repo-scoped item and does not mix the private note into shared root state.
16. `WATCHLIST.md에 추가해줘. 오늘 17:00에 배포 결과 확인.`
    - Expected: when both root `WATCHLIST.md` and `.watchlist/WATCHLIST.md` already exist and scope is unclear, mentions the split and avoids mutating either file until the target is clear.
