# Repository instructions

## Production deployments

- Production is deployed only through the GitHub integration, from the latest `origin/main` commit.
- Every change to publish, including recovered local work, must be committed, validated and integrated into GitHub `main` before deployment.
- Never deploy a local checkout, uncommitted files, another branch or an older revision to production. Do not use Vercel CLI deployment, promotion, alias or redeploy commands to publish.
- Before publishing, fetch `origin/main`, confirm the complete intended web changes are included, and check for local changes or another production version that would otherwise be lost.
- Trigger production through a GitHub push to `main`; verify the Vercel deployment is linked to that exact GitHub commit and check the public site after it completes.
- For an explicit redeployment of the latest `main` without code changes, use a GitHub commit that the repository deployment filter recognizes. Never redeploy an old Vercel deployment.
