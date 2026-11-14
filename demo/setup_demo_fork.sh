#!/usr/bin/env bash
# Sets up the live demo on GitHub: a fork of the challenge repository whose
# four AI-written branches are open as pull requests, each reviewed by the
# Earned-Trust workflow on its own.
#
#   demo/setup_demo_fork.sh [OWNER]        (default: the gh user)
#
# What it does, in order (nothing is pushed to the original repository):
#   1. forks te-industry-tech-office/junction26-messagepack-csharp into OWNER
#   2. makes a branch `ju26-base` at the commit the four branches start from,
#      with templates/earned-trust.yml and templates/gitattributes on it (and
#      without MessagePack's own CI workflows, so only the review runs)
#   3. makes ju26-base the fork's default branch (comment workflows run from it),
#      turns Actions on, and requires the check earned-trust/human-accountability-gate
#   4. pushes the four ju26-issue-* branches and opens one PR each into ju26-base
#
# Needs: gh (logged in), git, and the clone at ../junction26-messagepack-csharp
# (or MP_CLONE=path). Running it twice is safe: what exists is left as it is.
set -euo pipefail

UPSTREAM=te-industry-tech-office/junction26-messagepack-csharp
OWNER="${1:-$(gh api user -q .login)}"
FORK="$OWNER/junction26-messagepack-csharp"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MP="${MP_CLONE:-$HERE/../junction26-messagepack-csharp}"
BASE_SHA=32258fdbee4bcd653c79f51b4376b5103c6f4d27   # parent of all four ju26 commits
BRANCHES=(ju26-issue-2297 ju26-issue-2129 ju26-issue-2283 ju26-issue-2234)

[ -d "$MP/.git" ] || git clone --filter=blob:none "https://github.com/$UPSTREAM.git" "$MP"
git -C "$MP" fetch -q origin "${BRANCHES[@]}"

echo "1. fork $FORK"
gh repo view "$FORK" >/dev/null 2>&1 || gh repo fork "$UPSTREAM" --clone=false --fork-name junction26-messagepack-csharp
until gh repo view "$FORK" >/dev/null 2>&1; do sleep 2; done
git -C "$MP" remote get-url demo >/dev/null 2>&1 || git -C "$MP" remote add demo "https://github.com/$FORK.git"
# never push anywhere but the fork
git -C "$MP" remote set-url --push origin DISABLED-push-to-upstream

echo "2. ju26-base with the workflow"
WT="$(mktemp -d)"
git -C "$MP" worktree add -q --detach "$WT" "$BASE_SHA"
# only our workflow runs on the demo PRs: MessagePack's own CI stays out of it
git -C "$WT" rm -q -r --ignore-unmatch .github/workflows
mkdir -p "$WT/.github/workflows"
cp "$HERE/templates/earned-trust.yml" "$WT/.github/workflows/earned-trust.yml"
cat "$HERE/templates/gitattributes" >> "$WT/.gitattributes"
git -C "$WT" add -A .github/workflows .gitattributes
git -C "$WT" -c user.name="$(git config user.name)" -c user.email="$(git config user.email)" \
  commit -q -m "Earned-Trust review on every pull request"
git -C "$WT" push -q -f demo HEAD:refs/heads/ju26-base
git -C "$MP" worktree remove --force "$WT"

echo "3. default branch, Actions, required check"
gh repo edit "$FORK" --default-branch ju26-base >/dev/null
gh api -X PUT "repos/$FORK/actions/permissions" -F enabled=true -f allowed_actions=all >/dev/null
gh api -X PUT "repos/$FORK/branches/ju26-base/protection" --input - >/dev/null <<'JSON'
{"required_status_checks": {"strict": false, "contexts": ["earned-trust/human-accountability-gate"]},
 "enforce_admins": false, "required_pull_request_reviews": null, "restrictions": null}
JSON

echo "4. the four branches as PRs"
for b in "${BRANCHES[@]}"; do
  git -C "$MP" push -q -f demo "refs/remotes/origin/$b:refs/heads/$b"
  if [ -z "$(gh pr list --repo "$FORK" --head "$b" --state all -q '.[].number' --json number)" ]; then
    subject="$(git -C "$MP" log -1 --format=%s "origin/$b")"
    gh pr create --repo "$FORK" --base ju26-base --head "$b" --title "$subject" \
      --body "AI-written change from the Junction 2026 challenge (upstream issue ${b#ju26-issue-}). Reviewed by the Earned-Trust workflow." >/dev/null
  fi
done
gh pr list --repo "$FORK" --state open
echo "Done. Each PR runs the workflow on its own: https://github.com/$FORK/pulls"
