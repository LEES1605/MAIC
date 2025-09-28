# [AP-DISPATCH-FALLBACK] START: patch for src/ui/admin_prompt.py

def _repository_dispatch(owner: str, repo: str, token: str, yaml_text: str,
                         event_type: str = "publish-prompts") -> Dict[str, Any]:
    """
    GitHub repository_dispatch 폴백.
    해당 워크플로는 on.repository_dispatch.types: [publish-prompts] 를 가지고 있어야 동작.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"
    headers = _gh_headers(token)
    payload = {
        "event_type": event_type,
        "client_payload": {"prompts_yaml": yaml_text, "via": "admin-ui"}
    }
    r = req.post(url, headers=headers, json=payload, timeout=15)
    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok(repository_dispatch)"}
    raise RuntimeError(f"repository_dispatch 실패(status={r.status_code}): {r.text}")


def _dispatch_workflow(owner: str, repo: str, workflow: str, ref: str,
                       token: str, yaml_text: str, input_key: Optional[str]) -> Dict[str, Any]:
    """
    1) /actions/workflows/{workflow}/dispatches (workflow_dispatch)
    2) 422 'does not have workflow_dispatch' → /dispatches(repository_dispatch) 폴백
    3) 422 'Unexpected inputs' → 입력 없이 재시도
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = _gh_headers(token)

    def _post(payload): 
        return req.post(url, headers=headers, json=payload, timeout=15)

    payload: Dict[str, Any] = {"ref": ref}
    if input_key:
        payload["inputs"] = {input_key: yaml_text}
    r = _post(payload)

    # 성공
    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok"}

    # 422 처리
    try:
        js = r.json() if r.content else {}
        msg = (js.get("message") or "").lower()
    except Exception:
        js = {}
        msg = ""

    # 422: workflow_dispatch 트리거 자체 부재
    if r.status_code == 422 and "does not have 'workflow_dispatch'" in (js.get("message") or ""):
        # repository_dispatch 폴백 호출
        return _repository_dispatch(owner, repo, token, yaml_text, event_type="publish-prompts")

    # 422: Unexpected inputs → 입력 없이 재시도
    if r.status_code == 422 and "unexpected" in msg:
        r2 = _post({"ref": ref})
        if 200 <= r2.status_code < 300:
            return {"status": r2.status_code, "detail": "ok (fallback: no inputs)"}
        raise RuntimeError(f"workflow dispatch 실패(status={r2.status_code}): {r2.text}")

    # 그 외 에러
    raise RuntimeError(f"workflow dispatch 실패(status={r.status_code}): {js or r.text}")

# [AP-DISPATCH-FALLBACK] END
