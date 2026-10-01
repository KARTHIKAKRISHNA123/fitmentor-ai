#!/usr/bin/env bash
# Pushes a clean, history-free snapshot of your current branch to the
# Hugging Face Space. Usage (from the project folder, in Git Bash / UCRT64):
#
#     bash deploy_hf.sh            # uses the git remote named "space"
#
# Why a snapshot instead of a normal push? The Space starts with its own
# starter commit, and Hugging Face rejects pushes whose history contains
# binary files (the old .pyc files from early commits). A snapshot sidesteps
# both. Your GitHub history (remote "origin") is never touched.
set -euo pipefail

REMOTE="${1:-space}"

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "No git remote named '$REMOTE'. Add it first:"
  echo "  git remote add space https://huggingface.co/spaces/<your-username>/fitmentor-ai"
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "You have uncommitted changes - commit them first (see README section 10)."
  git status --short
  exit 1
fi

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo ".env is still tracked by git. Run README section 10 first so your API keys can never be pushed."
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"

# Whatever happens below (e.g. a wrong password), always come back to the
# original branch and remove the temporary one.
cleanup() {
  git checkout -q "$CURRENT_BRANCH" 2>/dev/null || true
  git branch -q -D hf-deploy 2>/dev/null || true
}
trap cleanup EXIT

git checkout -q --orphan hf-deploy
git rm -r -q --cached .
git add -A
git commit -q -m "Deploy FitMentor AI (from $CURRENT_BRANCH @ $SHORT_SHA)"

echo "Pushing snapshot to '$REMOTE' (use a Hugging Face WRITE token as the password)..."
git push "$REMOTE" hf-deploy:main --force

echo "Done. Open your Space and watch the 'Logs' tab while it builds."
