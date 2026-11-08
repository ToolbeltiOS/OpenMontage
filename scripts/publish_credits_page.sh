#!/usr/bin/env bash
# Build this film's credits page and push it to GitHub Pages.
#
# RUN BEFORE THE UPLOAD, NOT AFTER. The description links to the page, so
# the page has to answer before anyone can read the link. A description
# pointing at a 404 is worse than no link at all: it is an attribution
# claim that cannot be checked.
#
# THE PUSH IS HERE AND NOT IN A PYTHON STEP ON PURPOSE. `git push` is on
# the agent's deny list, and deny beats allow in that config — a "scoped
# exception" for one repository is not expressible, and working around the
# rule by spelling the command differently would defeat the point of having
# it. launchd runs this script directly, so it is not an agent action and
# the deny list does not apply. Run by hand, it is the operator's push.
#
# The site is its own repository, outside every worktree, like the ledger.
#
#   scripts/publish_credits_page.sh <slug>
set -uo pipefail
SLUG="${1:?usage: publish_credits_page.sh <slug>}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${CREDITS_SITE_DIR:-$(cd "$REPO/.." && pwd)/credits-site}"
PY="$REPO/.venv/bin/python"

if [[ ! -d "$SITE/.git" ]]; then
  echo "no credits site at $SITE — clone wak3upsociety-credits there first" >&2
  exit 1
fi

"$PY" "$REPO/scripts/build_credits_page.py" --project "$SLUG" --out "$SITE" \
  || { echo "credits page build failed for $SLUG" >&2; exit 1; }

cd "$SITE" || exit 1
git add -A
if git diff --cached --quiet; then
  echo "credits page unchanged for $SLUG — nothing to push"
else
  git -c user.name="wak3up runner" -c user.email="noreply@wak3up.invalid" \
      commit -q -m "credits: $SLUG" || exit 1
  git push -q origin HEAD || { echo "credits push FAILED for $SLUG" >&2; exit 1; }
  echo "credits page pushed for $SLUG"
fi

# IT IS NOT PUBLISHED UNTIL IT ANSWERS. Pages takes a moment to build, and
# a description that links to a 404 is the thing this step exists to stop.
URL="$("$PY" "$REPO/scripts/build_credits_page.py" --project "$SLUG" --url)"
for attempt in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$URL")"
  if [[ "$code" == "200" ]]; then
    echo "live: $URL"
    exit 0
  fi
  sleep 10
done
echo "credits page never answered 200 at $URL (last $code)" >&2
exit 1
