#!/usr/bin/env bash
# Milestone 0 live API verification for curiosity-radar.
# Run this on a machine with normal internet access (NOT the cloud sandbox —
# that's what hit the egress block in the first place).
#
# Usage:
#   chmod +x milestone0_verify.sh
#   ./milestone0_verify.sh
#
# Saves every raw response under ./milestone0-responses/. When it's done,
# paste back either the full terminal output, or the contents of the JSON
# files, so they can be turned into tests/cassettes/ fixtures and used to
# update curiosity-radar/references/api-notes.md.

set -uo pipefail

UA="curiosity-radar/0.1 (https://github.com/binskea/topic-scout; contact: marina@binskea.com)"
OUT="./milestone0-responses"
mkdir -p "$OUT"

req() {
  # req <label> <output-file> <url>
  local label="$1" file="$2" url="$3"
  local headers="$OUT/${file%.json}_headers.txt"
  curl -sS -D "$headers" -A "$UA" "$url" -o "$OUT/$file"
  local code
  code=$(head -1 "$headers" | tr -d '\r')
  echo "[$label] $code  -> $OUT/$file"
}

echo "== Milestone 0 verification =="
echo

echo "-- 1. Per-article, ordinary case (en.wikipedia, Intermittent_fasting, Aug 2024) --"
req "1-ordinary" "01_per_article_ordinary.json" \
  "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/20240801/20240831"

echo "-- 2. Per-article, low-traffic technical topic (look for zero-view day gaps) --"
req "2-low-traffic" "02_per_article_low_traffic.json" \
  "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Theil%E2%80%93Sen_estimator/daily/20240801/20240831"

echo "-- 3. Per-article for a title that is itself a redirect (USA -> United States) --"
req "3-redirect-title" "03_per_article_redirect_title.json" \
  "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/USA/daily/20240801/20240807"

echo "-- 4. Aggregate traffic, en.wikipedia, same range as #1 --"
req "4-aggregate" "04_aggregate.json" \
  "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/all-access/user/daily/20240801/20240831"

echo "-- 5. Wikidata search, deliberately ambiguous query ('Mercury') --"
req "5-wikidata-ambiguous" "05_wikidata_search_ambiguous.json" \
  "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Mercury&language=en&format=json&limit=10"

echo "-- 6. Wikidata sitelinks for Q1631107 (intermittent fasting) --"
req "6-wikidata-sitelinks" "06_wikidata_sitelinks.json" \
  "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1631107&props=sitelinks&format=json"

echo "-- 7a. MediaWiki title resolution, normal title --"
req "7a-mediawiki-normal" "07a_mediawiki_normal.json" \
  "https://en.wikipedia.org/w/api.php?action=query&titles=Python%20(programming%20language)&redirects=1&format=json"

echo "-- 7b. MediaWiki redirect resolution, single redirect (USA) --"
req "7b-mediawiki-single-redirect" "07b_mediawiki_single_redirect.json" \
  "https://en.wikipedia.org/w/api.php?action=query&titles=USA&redirects=1&format=json"

echo "-- 7c. MediaWiki redirect resolution, Ukrainian topic (Astronomy), non-Latin script check --"
req "7c-mediawiki-uk" "07c_mediawiki_uk.json" \
  "https://uk.wikipedia.org/w/api.php?action=query&titles=%D0%90%D1%81%D1%82%D1%80%D0%BE%D0%BD%D0%BE%D0%BC%D1%96%D1%8F&redirects=1&format=json"

echo "-- 8. Repeat call #1 to sanity-check short-interval response stability --"
req "8-repeat" "08_per_article_repeat.json" \
  "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/20240801/20240831"
if diff -q "$OUT/01_per_article_ordinary.json" "$OUT/08_per_article_repeat.json" > /dev/null; then
  echo "    identical to call #1 (good sign, though a real closed-month stability"
  echo "    check needs a longer gap than this script can provide in one run)"
else
  echo "    DIFFERS from call #1 -- worth a look"
fi

echo "-- 9. Small parallel burst (5 concurrent) to gauge rate-limit behavior --"
echo "    (kept deliberately small -- this is a courtesy check, not a load test)"
for i in 1 2 3 4 5; do
  curl -sS -o "$OUT/09_burst_$i.json" -D "$OUT/09_burst_${i}_headers.txt" -A "$UA" \
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/all-access/user/daily/20240801/20240807" &
done
wait
for i in 1 2 3 4 5; do
  code=$(head -1 "$OUT/09_burst_${i}_headers.txt" | tr -d '\r')
  echo "    burst $i: $code"
done

echo "-- 10. Earliest-date probe (request starting well before AQS's believed 2015-07 start) --"
req "10-earliest-date" "10_earliest_date_probe.json" \
  "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/20100101/20100107"

echo
echo "Done. Everything is under $OUT/."
echo "Please paste back the terminal output above, plus the contents of the"
echo "JSON files (or just tar/zip the $OUT/ directory and share it) so these"
echo "can become tests/cassettes/ fixtures and update"
echo "curiosity-radar/references/api-notes.md from [UNVERIFIED-LIVE] to [CONFIRMED]."
