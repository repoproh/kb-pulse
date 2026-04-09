.PHONY: install run run-strobe run-bass devices lint clean

install:
	pip install .

run:
	python3 kb_pulse.py

run-strobe:
	python3 kb_pulse.py --mode strobe

run-bass:
	python3 kb_pulse.py --mode bass_hit --sensitivity 1.5

devices:
	python3 kb_pulse.py --list-devices

lint:
	python3 -m py_compile kb_pulse.py
	@echo "Syntax OK"

clean:
	rm -rf build/ dist/ *.egg-info __pycache__
