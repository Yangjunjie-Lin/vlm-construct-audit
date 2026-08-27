.PHONY: minimum-loop scientific-pilot tier0-5-triage post-stop-screen test

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

test:
	pytest
