# WATCHLIST.md

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/dd3ok/WATCHLIST.md)](https://github.com/dd3ok/WATCHLIST.md/blob/main/LICENSE)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/dd3ok/WATCHLIST.md/ci.yml?branch=main)](https://github.com/dd3ok/WATCHLIST.md/actions/workflows/ci.yml)

[English README](README.md)

`WATCHLIST.md`는 deferred check를 기록하기 위한 경량 **AI Agent Skill**이자 AgentSkills 호환 Markdown workflow입니다. Codex, Claude Code, OpenClaw, Gemini CLI, Kilo, Hermes가 CI 후속 확인, 배포 검증, PR 확인, 티켓, 작업, 데이터 동기화, 이메일을 scheduler, daemon, database, MCP server 없이 추적하도록 돕습니다.

이 스킬은 자율 스케줄러, 자율 알림, daemon, database, cron job, UI, background worker가 아닙니다. 나중에 확인할 일을 기록할 뿐이며, 스스로 깨어나거나 polling, 알림, 확인 실행을 하지 않습니다.

## Quickstart

스킬 디렉토리를 설치합니다:

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

에이전트에게 요청합니다:

```text
WATCHLIST.md에 추가해줘. 오늘 17:00에 GitHub Actions 결과 확인.
```

이 source repo의 예시 워치리스트를 검증합니다:

```bash
python3 evals/check_watchlist.py examples/WATCHLIST.example.md
```

## Skill Directory

리포지토리 루트가 아니라 `SKILL.md`가 루트에 있는 스킬 디렉토리를 설치하거나 복사하세요:

```text
.agents/skills/watchlist-md
```

runtime bundle에는 스킬 지시문, 템플릿, OpenAI 메타데이터, 짧은 reference가 들어갑니다:

```text
.agents/skills/watchlist-md/SKILL.md
.agents/skills/watchlist-md/assets/WATCHLIST.template.md
.agents/skills/watchlist-md/agents/openai.yaml
.agents/skills/watchlist-md/references/format.md
.agents/skills/watchlist-md/references/lifecycle.md
.agents/skills/watchlist-md/references/safety.md
```

repository-only checks, examples, maintainer docs는 설치 가능한 스킬 디렉토리 밖에 둡니다.

## What It Does / Does Not Do

에이전트가 CI, 배포, PR, 티켓, 작업, 데이터 동기화, 주문, 결제, 이메일 후속 확인을 나중에 검토하도록 기록해야 할 때 사용하세요.

Markdown 편집으로 add, review, complete, blocked, snoozed, dropped, explicit delete, explicit archive workflow를 지원합니다.

하지 않는 일:

- 확인 작업 자동 실행
- reminder 또는 wakeup 전송
- issue tracker, incident system, project management tool 대체
- secret, signed URL, raw log, raw email, private excerpt 저장
- 명시적 권한과 설정된 접근 수단 없이 private system 접근

## Runtime Weight

설치 가능한 runtime skill은 Python-free입니다. 에이전트는 스킬 계약에 따라 Markdown을 직접 편집하고, 이 source repo만 `tools/validate_watchlist.py`와 `evals/`에 결정적 검증을 둡니다.

`.agents/skills/watchlist-md/`에 CLI, MCP server, browser automation, bundled validator, smoke transcript, screenshot, 긴 eval corpus를 넣지 마세요.

Gemini CLI, Kilo, OpenClaw, Hermes 같은 AgentSkills 호환 런타임은 가능하면 같은 스킬 디렉토리를 사용하세요. OpenClaw와 Hermes는 runtime smoke 전까지 AgentSkills 호환/manual 지원으로 보고, 리포지토리 루트가 아니라 `SKILL.md`가 루트에 있는 스킬 디렉토리를 설치하세요.

## Docs

- [Installation](docs/install.md): Codex, Claude Code, OpenAI Skills zip packaging, AgentSkills-compatible runtime notes.
- [Storage and privacy](docs/storage-and-privacy.md): generated `.watchlist/WATCHLIST.md`, shared root watchlists, archive policy, concurrent edits, retention.
- [Validation](docs/validation.md): validator commands, strict-safety behavior, semantic cases, item format expectations.
- [Runtime smoke](docs/runtime-smoke.md): transcript나 raw log 없는 compact vendor/runtime smoke matrix.
- [Maintainer release checklist](docs/maintainers/release.md): package boundary, release metadata, pre-PR checks.
- [Maintainer self-checks](docs/maintainers/self-checks.md): maintainer용 repo-only review prompts.
