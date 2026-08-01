"""list_repos tool — list all ingested repositories."""

from __future__ import annotations

from codegraph.models.tools import ListReposResult, RepoInfo
from codegraph.repo.port import CodeGraphRepository


async def list_repos(repo: CodeGraphRepository) -> ListReposResult:
    rows = await repo.list_repos()
    return ListReposResult(repos=[RepoInfo(**r) for r in rows])
