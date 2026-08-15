run-dev-api:
	fastapi dev api/main.py --reload --port 8000

run-dev-ui:
	cd ui && bun run dev

build-ui:
	cd ui && bun run generate

test-basic-search:
	python api/app/tools/search.py "Guatemala City, Guatemala" --checkin 2026-10-01 --nights 5 -k "suana" -a gym pool --match-all --max-price 500 --guests 1 -o tokyo.json

login:
	gcloud auth login

deploy:
	set -a && source .env && set +a

	gcloud run deploy homey \
	--source . \
	--project bohemdev \
	--region us-east1 \
	--allow-unauthenticated \
	--memory 1Gi \
	--cpu 1 \
	--timeout 300 \
	--set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY},DB_URL=${DB_URL},DB_TOKEN=${DB_TOKEN},SEARCH_MAX_LISTINGS=${SEARCH_MAX_LISTINGS},SEARCH_TOP_K=${SEARCH_TOP_K}"