# WATCHLIST.md

schema_version: 1
automation: none
timezone: Asia/Seoul

## Open

## Done

### WL-20260401-001 — 완료된 배포 확인
- status: done
- priority: P2
- owner: assistant_on_review
- due_at: 2026-04-01T17:00:00+09:00
- created_at: 2026-04-01T16:30:00+09:00
- source: deployment run 123
- trigger: Deployment result needed follow-up
- action: 배포 결과 확인
- done_when: 배포 결과가 기록됨
- last_checked_at: 2026-04-01T17:10:00+09:00
- result: Deployment passed
- next_step_on_fail:

### WL-20260401-002 — 취소된 후속 확인
- status: dropped
- priority: P3
- owner: user
- due_at: 2026-04-01T18:00:00+09:00
- created_at: 2026-04-01T16:45:00+09:00
- source: conversation note
- trigger: Follow-up was initially requested
- action: 취소된 후속 확인
- done_when: 더 이상 확인이 필요 없음
- last_checked_at:
- result: User dropped the follow-up
- next_step_on_fail:

## Archive
