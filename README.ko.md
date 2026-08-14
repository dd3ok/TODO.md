# WATCHLIST.md

[English](README.md)

`watchlist-md`는 나중에 명시적으로 검토할 확인 작업을 Markdown에 기록하는
경량 Agent Skill입니다. 스스로 깨어나거나 polling, 알림, 백그라운드 실행을
하지 않습니다.

## 설치

저장소 루트가 아니라 스킬 디렉터리를 설치합니다.

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

```text
WATCHLIST.md에 추가해줘. 오늘 17:00에 GitHub Actions 결과 확인.
```

수동 설치는 `.agents/skills/watchlist-md` 전체를 대상 런타임이 지원하는 스킬
디렉터리에 복사합니다. 자세한 내용은 [설치 문서](docs/install.md)를 참고하세요.

기본 저장 위치는 비공개 작업 메모인 `.watchlist/WATCHLIST.md`입니다. Git 작업
트리에서는 저장소 로컬 exclude로 이 경로를 추적 대상에서 제외합니다. 루트
`WATCHLIST.md`는 사용자가 팀 공유 상태로 명시한 경우에만 사용합니다. 여기서
비공개란 로컬·미추적이라는 뜻이며 암호화나 접근 제어를 뜻하지 않습니다.

비밀정보, 원문 형태의 비공개 내용, 인증정보가 포함된 링크는 저장하지 않습니다.
기록 자체가 배포, 결제, 외부 메시지 전송 같은 고위험 작업의 실행 권한이 되지는
않습니다.

## 스키마 v2

두 표준 작업공간 경로에서 서로 겹치지 않는 `WL-YYYYMMDD-NNN` ID와 `open`,
`blocked`, `done`, `dropped` 상태를 사용합니다.

```md
# WATCHLIST.md

schema_version: 2
timezone: Asia/Seoul

## Open

### WL-20260813-001 - CI 결과 확인
- status: open
- due_at: 2026-08-13T17:00:00+09:00
- created_at: 2026-08-13T16:30:00+09:00
- source: PR #123
- action: GitHub Actions 결과 확인
- done_when: 전체 통과 또는 실패 원인 기록

## Done
```

`priority`는 선택 필드이며 사용할 때는 `P0`부터 `P3`까지 씁니다. `owner`도
선택 필드입니다. `blocked`, `done`, `dropped` 항목에는 `last_checked_at`과
`result`가 필요합니다. `## Archive`는 명시적으로 보관한 `done` 또는 `dropped`
항목에만 사용합니다.

재일정은 활성 항목의 `open` 또는 `blocked` 상태를 유지합니다. `done`이나
`dropped` 항목을 재일정하려면 재개 여부를 먼저 확인합니다.

스키마 v2만 지원합니다. 다른 스키마를 해석하거나 마이그레이션하지 않습니다.
자세한 규칙은 [validation 문서](docs/validation.md)를 참고하세요.

## 검증

설치되는 스킬은 Python 없이 동작합니다. 저장소의 결정적 검증만 Python 표준
라이브러리를 사용합니다.

```bash
python -B -m unittest discover -s evals -p 'test_*.py'
python -B tools/validate_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md
```

단위 테스트는 스킬 메타데이터를 포함한 파일·패키지 인터페이스를 검증합니다.
샌드박스를 유지한 로컬 핵심 runtime smoke에서 발견, 명시·암시 호출, 추가,
읽기 전용 검토, 완료 전환, 일반 요청 부정 라우팅, 중복 ID와 미지원 스키마의
쓰기 전 중단을 확인했습니다. 전체 수동 코퍼스는 아직 실행하지 않았습니다.
범위, 설정, 근거와 재현할 수 없는 과거 관찰은
[runtime smoke 문서](docs/runtime-smoke.md)에 분리해 두었습니다.
