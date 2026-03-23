---
phase: 6
slug: walking-the-talk-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — use inline pytest |
| **Quick run command** | `python -c "from finsight.credisentiment.service import walk_the_talk; print('import OK')"` |
| **Full suite command** | `python -m pytest tests/ -x -q 2>/dev/null || python -c "from finsight.credisentiment import service; print('module OK')"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick import check
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | WTT-03, WTT-04 | integration | `python -c "from finsight.credisentiment.service import walk_the_talk; print('OK')"` | ✅ | ⬜ pending |
| 06-01-02 | 01 | 1 | WTT-07 | unit | `grep -c "ClaimCategory" finsight/models/enums.py` | ✅ | ⬜ pending |
| 06-01-03 | 01 | 1 | WTT-10 | unit | `python -c "from finsight.credisentiment.service import _parse_deepseek_thinking; print('OK')"` | ✅ | ⬜ pending |
| 06-01-04 | 01 | 1 | PERF-01 | integration | `grep -c "AsyncClient\|asyncio.to_thread" finsight/credisentiment/service.py` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 1 | WTT-01, WTT-02 | integration | `grep -c "compare\|walk.the.talk" finsight/credisentiment/router.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Document picker shows only cs_status=indexed docs | WTT-02 | Requires frontend rendering | Open WTT tab, verify only CrediSentiment-processed docs appear |
| Two-stage extraction produces meaningful claims | WTT-03 | LLM output quality | Run analysis on real con-call + earnings pair, verify claim extraction |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
