.PHONY: minimum-loop scientific-pilot test

minimum-loop:
	python -m vlm_construct_audit minimum-loop

scientific-pilot:
	python -m vlm_construct_audit run-pilot

test:
	pytest

