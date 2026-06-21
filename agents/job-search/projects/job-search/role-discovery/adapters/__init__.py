"""Adapter registry. Each adapter exports `fetch(company_name, slug, **opts) -> List[Role]`."""
from . import greenhouse, ashby, lever, workday, smartrecruiters
from . import microsoft, google, apple, meta, eightfold
from . import linkedin, rippling, uber, snap, bytedance, workable
from . import jobright, bamboohr
from . import remotive, remoteok, himalayas

REGISTRY = {
    "greenhouse": greenhouse.fetch,
    "ashby": ashby.fetch,
    "lever": lever.fetch,
    "workable": workable.fetch,
    "workday": workday.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "bamboohr": bamboohr.fetch,
    "himalayas": himalayas.fetch,
    "eightfold": eightfold.fetch,
    "microsoft": microsoft.fetch,
    "google": google.fetch,
    "apple": apple.fetch,
    "meta": meta.fetch,
    "linkedin": linkedin.fetch,
    "rippling": rippling.fetch,
    "uber": uber.fetch,
    "snap": snap.fetch,
    "bytedance": bytedance.fetch_bytedance,
    "tiktok": bytedance.fetch_tiktok,
    "jobright": jobright.fetch,
    "remotive": remotive.fetch,
    "remoteok": remoteok.fetch,
}
