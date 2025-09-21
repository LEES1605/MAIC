# ===== [PATCH] FILE: src/ui/widgets/index_status.py — restore call — START =====
from src.runtime.gh_release import GHConfig, GHError, GHReleases, RestoreLog

# ...
res = gh.restore_latest_index(
    tag_candidates=tag_candidates,
    asset_candidates=asset_candidates,
    dest=dest_dir,
    clean_dest=True,
)
if isinstance(res, RestoreLog):
    rtag, rid, detail = res.tag, res.release_id, res.detail
else:  # very old fallback (string)
    rtag, rid, detail = getattr(res, "tag", None), getattr(res, "release_id", None), str(getattr(res, "detail", res))
# 이후 메타 저장/세션 갱신은 동일
# ===== [PATCH] FILE: src/ui/widgets/index_status.py — restore call — END =====
