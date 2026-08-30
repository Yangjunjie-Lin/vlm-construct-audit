.PHONY: minimum-loop scientific-pilot tier0-5-triage post-stop-screen construct-v2-preaudit test

minimum-loop:
	python -m vlm_construct_audit minimum-loop

scientific-pilot:
	python -m vlm_construct_audit run-pilot

tier0-5-triage:
	python -m vlm_construct_audit run-loop-a
	python -m vlm_construct_audit run-loop-b
	python -m vlm_construct_audit run-loop-c
	python -m vlm_construct_audit adjudicate-tier0-5

post-stop-screen:
	python -m vlm_construct_audit post-stop-freeze
	@echo "Sealed holdouts are intentionally not run by this target. Use the direction-specific commands only after freeze and authorization records exist."

construct-v2-preaudit:
	python -m vlm_construct_audit retire-p-mini-pilot-v1
	python -m vlm_construct_audit analyze-construct-v2-power
	python -m vlm_construct_audit generate-construct-v2
	python -m vlm_construct_audit validate-construct-v2
	python -m vlm_construct_audit audit-construct-v2-leakage
	python -m vlm_construct_audit run-construct-v2-oracles
	python -m vlm_construct_audit build-construct-v2-review-packet
	python -m vlm_construct_audit verify-no-construct-v2-inference
	python -m vlm_construct_audit build-construct-v2-report

test:
	pytest
