.PHONY: up down logs waste-on waste-off traffic audit apply verify unapply demo ui restore-baseline test

up:            ## start collector + victim stack + auditor + ui (SigNoz runs separately)
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

waste-on:      ## arm all WASTE_* toggles and restart victim services
	./scripts/toggle_waste.sh on

waste-off:
	./scripts/toggle_waste.sh off

traffic:       ## load generator (keep running in a spare terminal from Day 1)
	python3 scripts/traffic.py

audit:         ## run a full audit, print findings table
	curl -s -X POST localhost:$${AUDITOR_PORT:-8100}/audit | python3 -m json.tool

apply:         ## make apply F=T2 — apply generated fix for a finding, reload collector
	@test -n "$(F)" || (echo "usage: make apply F=<finding-id>" && exit 1)
	curl -s -X POST localhost:$${AUDITOR_PORT:-8100}/apply/$(F) | python3 -m json.tool

verify:        ## make verify F=T2 — before/after volumes + dashboard/alert integrity sweep
	@test -n "$(F)" || (echo "usage: make verify F=<finding-id>" && exit 1)
	curl -s -X POST localhost:$${AUDITOR_PORT:-8100}/verify/$(F) | python3 -m json.tool

unapply:       ## make unapply F=T2 — remove a patch and reload (reversibility demo)
	@test -n "$(F)" || (echo "usage: make unapply F=<finding-id>" && exit 1)
	curl -s -X POST localhost:$${AUDITOR_PORT:-8100}/unapply/$(F) | python3 -m json.tool

restore-baseline:  ## panic button: baseline collector config, drop all patches, reload
	./scripts/restore_baseline.sh

demo:          ## seeded end-to-end rehearsal run (see docs/DEMO-SCRIPT.md)
	./scripts/demo.sh

test:          ## run the auditor unit tests (stdlib unittest — no extra deps; CH tests self-skip off-image)
	python3 -m unittest discover -s auditor/tests -t . -v

ui:
	cd ui && pnpm dev
