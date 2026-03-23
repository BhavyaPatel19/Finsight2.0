---
phase: 3
slug: credisentiment-processing-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (not currently installed — Wave 0 installs) |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/test_credisentiment_pipeline.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_credisentiment_pipeline.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PROC-02 | unit | `python -m pytest tests/test_credisentiment_pipeline.py::test_chunk_size_and_overlap -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | PROC-02 | unit | `python -m pytest tests/test_credisentiment_pipeline.py::test_section_boundary_chunking -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | PROC-03 | unit | `python -m pytest tests/test_credisentiment_pipeline.py::test_separate_collection -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | PROC-02+03 | integration | `python -m pytest tests/test_credisentiment_pipeline.py::test_pipeline_independence -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_credisentiment_pipeline.py` — stubs for PROC-02, PROC-03
- [ ] `tests/conftest.py` — shared fixtures (test DB session, temp ChromaDB dir)
- [ ] Framework install: `pip install pytest` — if not already in requirements

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
