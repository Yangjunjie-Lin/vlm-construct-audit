# Independent P3 Method-Lock Audit

Decision: `PASS_WITH_LIMITATIONS`—no substantive P3 error was found that would trigger
`AUDIT_FAIL_P3_METHOD_LOCK`.

The four locked source files independently match the normalized UTF-8/LF SHA-256 values in
`p_mini_pilot_method_lock.yaml`. The source commit and frozen source-state commit exist. The method
uses `delta0=0.10`, `delta1=0.15`, a 1.9599639845 certification critical value, a 1.644853627
below-SESOI critical value, explicit gray-zone output, and fail-first validity checks. Measurement
invalidity precedes contract/format dependence, partial identification, and uptake invalidity;
none of those states can be promoted to a positive claim. The development and holdout namespaces
are disjoint, threshold selection precedes the single sealed holdout, and the execution marker
records exactly one completed holdout.

The historical `method_freeze.yaml` stores the SHA-256 of the power table's then-Windows CRLF
working-tree bytes (`201ed2…`), while the current Git/LF-normalized bytes hash to `e49b10…`. The
content-normalized method lock explicitly records `e49b10…`, and all parsed numerical values are
unchanged. This is a line-ending provenance blemish, not a numerical method change.

Limitations retained by the audit:

- P3 is a prechecked normal-approximation three-way decision rule. The source does not implement a
  conformal guarantee for real VLM outcomes, and the frozen text correctly forbids transporting
  such a guarantee.
- The known-DGP sensitivity and threshold-stability gates depend on the registered family mixture
  and on synthetic discordance rules. They do not establish real-VLM discordance or overall
  six-cell power.
- Valid P3 rows normally end as positive, below-SESOI, or explicit gray; they do not use
  `INCONCLUSIVE`. Later GO/NO-GO prose that counts INCONCLUSIVE cells is therefore poorly aligned
  with the locked implementation, but it does not change P3's numerical decision itself.
- The code's “risk-coverage” label should not be interpreted as identifying an internal mechanism
  or as a distribution-free real-VLM certificate.

The known-DGP holdout was not rerun or reselected during this audit.
