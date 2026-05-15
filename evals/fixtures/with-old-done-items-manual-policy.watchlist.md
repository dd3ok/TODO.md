# WATCHLIST.md

schema_version: 1
automation: none
timezone: Asia/Seoul
archive_policy: manual

## Open

### WL-20260515-001 — 배포 결과 확인
- status: open
- priority: P1
- owner: assistant_on_review
- due_at: 2026-05-15T17:00:00+09:00
- created_at: 2026-05-15T10:00:00+09:00
- source: deployment dashboard run 456
- trigger: deployment was still running
- action: 배포 결과 확인
- done_when: 배포 성공 또는 실패 원인 기록
- last_checked_at:
- result:
- next_step_on_fail: 실패 로그를 요약하고 사용자에게 수정 여부 확인

## Done

### WL-20260401-001 — 오래된 CI 결과 확인
- status: done
- priority: P2
- owner: assistant_on_review
- due_at: 2026-04-01T17:00:00+09:00
- created_at: 2026-04-01T16:30:00+09:00
- source: GitHub Actions run for PR #101
- trigger: CI was pending
- action: CI 결과 확인
- done_when: 모든 job pass 또는 실패 원인 기록
- last_checked_at: 2026-04-01T17:05:00+09:00
- result: 모든 job pass
- next_step_on_fail:

### WL-20260402-001 — 취소된 외부 응답 확인
- status: dropped
- priority: P3
- owner: user
- due_at: 2026-04-02T17:00:00+09:00
- created_at: 2026-04-02T16:30:00+09:00
- source: support ticket ABC-123
- trigger: external reply was pending
- action: 외부 응답 확인
- done_when: 응답 도착 또는 사용자 취소
- last_checked_at:
- result: 사용자가 더 이상 필요 없다고 판단
- next_step_on_fail:

## Archive
