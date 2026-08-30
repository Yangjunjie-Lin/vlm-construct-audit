"""Run the frozen v2 leakage audit without model inference."""

from __future__ import annotations

import json

from vlm_construct_audit.construct_v2.leakage import audit_construct_v2_leakage

if __name__ == "__main__":
    print(json.dumps(audit_construct_v2_leakage(), indent=2, sort_keys=True))

