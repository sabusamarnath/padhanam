# Audit Log

One entry per audit. Audits happen at phase boundaries. Format is structured to keep audits scannable.

Format:
```
## Audit N (end of Phase X)
- Decisions reviewed: [count, any flagged for revisit]
- Schema check: [in sync / drift found and resolved]
- Test coverage: [summary]
- Metric scope: [in scope / new metrics added with justification]
- Security posture: [pass / items raised]
- Drift findings: [list, or "none"]
- Operating model adjustments: [list, or "none"]
- Next phase direction: [decided / deferred]
```

---
