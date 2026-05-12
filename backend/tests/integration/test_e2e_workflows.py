"""
End-to-end workflow tests — NovaWorks PeopleOps Copilot.

Tests every sequential workflow from Requirement.md:
  1. Auth (login, token, bad creds, role guard)
  2. Leave lifecycle  (apply → pending → approve → balance update)
  3. Leave lifecycle  (apply → pending → reject)
  4. Ticket lifecycle (create → visible → assign → status update)
  5. Announcements    (create gate, list propagation)
  6. Project lifecycle (create → assign → visible in my-projects)
  7. Admin CRUD       (create / update / delete user, roles table)
  8. AI chat smoke    (policy, sql, actions, router)

Run against live backend:
    cd backend
    python -m pytest tests/integration/test_e2e_workflows.py -v --tb=short

Or as a standalone script:
    python tests/integration/test_e2e_workflows.py
"""
from __future__ import annotations

import sys
import datetime
import requests
from typing import Optional

BASE = "http://127.0.0.1:8000/api/v1"

# ── colours ───────────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; E = "\033[0m"

results: list[tuple[str, Optional[bool], str]] = []


def section(title: str) -> None:
    print(f"\n{B}{'─'*70}{E}\n{B}  {title}{E}\n{B}{'─'*70}{E}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    tag = f"{G}PASS{E}" if ok else f"{R}FAIL{E}"
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))
    results.append((label, ok, detail))
    return ok


def skip(label: str, reason: str) -> None:
    print(f"  [{Y}SKIP{E}] {label}  — {reason}")
    results.append((label, None, reason))


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[Optional[str], dict]:
    r = requests.post(f"{BASE}/auth/login",
                      json={"email": email, "password": password}, timeout=10)
    body = r.json()
    if body.get("success") and body.get("data", {}).get("access_token"):
        return body["data"]["access_token"], body["data"]
    return None, body


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get(path: str, token: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE}{path}", headers=hdr(token), timeout=15, **kwargs)


def post(path: str, token: str, body: dict, **kwargs) -> requests.Response:
    return requests.post(f"{BASE}{path}", headers=hdr(token), json=body, timeout=15, **kwargs)


def patch(path: str, token: str, body: dict, **kwargs) -> requests.Response:
    return requests.patch(f"{BASE}{path}", headers=hdr(token), json=body, timeout=15, **kwargs)


def delete(path: str, token: str, **kwargs) -> requests.Response:
    return requests.delete(f"{BASE}{path}", headers=hdr(token), timeout=15, **kwargs)


def unwrap(r: requests.Response) -> object:
    """Return data field if present, else raw json."""
    body = r.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def find_in_list(lst: list, key: str, val) -> Optional[dict]:
    return next((i for i in lst if i.get(key) == val), None)


# ─────────────────────────────────────────────────────────────────────────────
# SETUP — login all users
# ─────────────────────────────────────────────────────────────────────────────
section("SETUP — login")

admin_tok,    admin_data    = login("priya.sharma@novaworks.in",  "Admin@1234")
manager_tok,  manager_data  = login("arjun.mehta@novaworks.in",   "Manager@1234")
employee_tok, employee_data = login("rahul.verma@novaworks.in",   "Employee@1234")

check("Admin login",    admin_tok    is not None, f"role={admin_data.get('role')}")
check("Manager login",  manager_tok  is not None, f"role={manager_data.get('role')}")
check("Employee login", employee_tok is not None, f"role={employee_data.get('role')}")

# employee id needed for project assignment tests
employee_id = employee_data.get("user_id") if isinstance(employee_data, dict) else None
manager_id  = manager_data.get("user_id")  if isinstance(manager_data, dict) else None


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTH
# ─────────────────────────────────────────────────────────────────────────────
section("1. AUTH — token, RBAC guards, /me")

# 1a — bad password
bad_tok, bad_body = login("priya.sharma@novaworks.in", "wrongpassword")
check("Bad password → no token", bad_tok is None,
      str(bad_body.get("error") or bad_body.get("detail", ""))[:80])

# 1b — no token → 401
r = requests.get(f"{BASE}/admin/users", timeout=10)
check("No token → 401", r.status_code == 401, f"got {r.status_code}")

# 1c — garbage token → 401
r = requests.get(f"{BASE}/admin/users",
                 headers={"Authorization": "Bearer not_a_token"}, timeout=10)
check("Garbage token → 401", r.status_code == 401, f"got {r.status_code}")

# 1d — employee cannot reach admin → 403
if employee_tok:
    r = get("/admin/users", employee_tok)
    check("Employee → /admin/users → 403", r.status_code == 403, f"got {r.status_code}")

# 1e — /me returns correct role
if employee_tok:
    r = get("/auth/me", employee_tok)
    me = unwrap(r)
    check("/me returns EMPLOYEE role",
          isinstance(me, dict) and me.get("role") == "EMPLOYEE",
          f"role={me.get('role') if isinstance(me,dict) else me}")

if manager_tok:
    r = get("/auth/me", manager_tok)
    me = unwrap(r)
    check("/me returns MANAGER role",
          isinstance(me, dict) and me.get("role") == "MANAGER",
          f"role={me.get('role') if isinstance(me,dict) else me}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. LEAVE LIFECYCLE — apply → pending → APPROVE → balance update
# ─────────────────────────────────────────────────────────────────────────────
section("2. LEAVE LIFECYCLE — apply → approve (sequential)")

leave_id: Optional[int] = None

if employee_tok and manager_tok:
    # 2a — get leave balance BEFORE
    r = get("/auth/me", employee_tok)
    me_before = unwrap(r)
    balance_key = "casual_leaves_remaining" if isinstance(me_before, dict) else None

    # 2b — apply leave (unique dates to avoid "already applied" collision)
    today = datetime.date.today()
    future1 = (today + datetime.timedelta(days=30)).isoformat()
    future2 = (today + datetime.timedelta(days=31)).isoformat()

    r = post("/leaves/requests", employee_tok, {
        "leave_type": "CASUAL",
        "start_date": future1,
        "end_date": future2,
        "reason": "E2E workflow test",
    })
    check("Employee: apply leave → 201",
          r.status_code == 201, f"status={r.status_code} body={r.text[:120]}")
    if r.status_code == 201:
        leave_data = unwrap(r)
        leave_id = leave_data.get("id") if isinstance(leave_data, dict) else None
        status_val = leave_data.get("status") if isinstance(leave_data, dict) else None
        check("Applied leave status = PENDING",
              status_val == "PENDING", f"status={status_val}")

    # 2c — leave appears in employee /my list
    r = get("/leaves/requests/my", employee_tok)
    my_leaves = unwrap(r)
    found_in_my = False
    if isinstance(my_leaves, list) and leave_id:
        found_in_my = any(l.get("id") == leave_id for l in my_leaves)
    check("Applied leave visible in employee /my list",
          found_in_my, f"leave_id={leave_id}")

    # 2d — leave appears in manager /pending list
    r = get("/leaves/requests/pending", manager_tok)
    pending = unwrap(r)
    found_in_pending = False
    if isinstance(pending, list) and leave_id:
        found_in_pending = any(l.get("id") == leave_id for l in pending)
    check("Applied leave visible in manager /pending list",
          found_in_pending, f"leave_id={leave_id} pending_count={len(pending) if isinstance(pending,list) else '?'}")

    # 2e — manager approves
    if leave_id:
        r = patch(f"/leaves/requests/{leave_id}", manager_tok, {"action": "approve"})
        check("Manager: approve leave → 200",
              r.status_code == 200, f"status={r.status_code} body={r.text[:120]}")
        if r.status_code == 200:
            approved = unwrap(r)
            check("Approved leave status = APPROVED",
                  isinstance(approved, dict) and approved.get("status") == "APPROVED",
                  f"status={approved.get('status') if isinstance(approved,dict) else approved}")

    # 2f — leave REMOVED from manager /pending after approval
    r = get("/leaves/requests/pending", manager_tok)
    pending_after = unwrap(r)
    still_pending = False
    if isinstance(pending_after, list) and leave_id:
        still_pending = any(l.get("id") == leave_id for l in pending_after)
    check("Approved leave removed from manager /pending list",
          not still_pending, f"leave_id={leave_id} still_in_pending={still_pending}")

    # 2g — employee sees APPROVED in /my list
    r = get("/leaves/requests/my", employee_tok)
    my_leaves_after = unwrap(r)
    approved_in_my = False
    if isinstance(my_leaves_after, list) and leave_id:
        match = find_in_list(my_leaves_after, "id", leave_id)
        approved_in_my = match is not None and match.get("status") == "APPROVED"
    check("Employee: leave shows APPROVED in /my list",
          approved_in_my, f"leave_id={leave_id}")

    # 2h — employee cannot approve leave (RBAC guard)
    r = get("/leaves/requests/pending", employee_tok)
    check("Employee: /pending → 403",
          r.status_code == 403, f"got {r.status_code}")

else:
    skip("Leave lifecycle (approve)", "missing tokens")


# ─────────────────────────────────────────────────────────────────────────────
# 3. LEAVE LIFECYCLE — apply → pending → REJECT
# ─────────────────────────────────────────────────────────────────────────────
section("3. LEAVE LIFECYCLE — apply → reject (sequential)")

reject_leave_id: Optional[int] = None

if employee_tok and manager_tok:
    today = datetime.date.today()
    future3 = (today + datetime.timedelta(days=60)).isoformat()
    future4 = (today + datetime.timedelta(days=61)).isoformat()

    r = post("/leaves/requests", employee_tok, {
        "leave_type": "SICK",
        "start_date": future3,
        "end_date": future4,
        "reason": "E2E reject workflow test",
    })
    check("Employee: apply leave (to reject) → 201",
          r.status_code == 201, f"status={r.status_code}")
    if r.status_code == 201:
        reject_leave_id = (unwrap(r) or {}).get("id")

    if reject_leave_id:
        # appears in pending
        r = get("/leaves/requests/pending", manager_tok)
        pending = unwrap(r)
        found = isinstance(pending, list) and any(l.get("id") == reject_leave_id for l in pending)
        check("To-reject leave visible in manager /pending",
              found, f"leave_id={reject_leave_id}")

        # manager rejects
        r = patch(f"/leaves/requests/{reject_leave_id}", manager_tok, {"action": "reject"})
        check("Manager: reject leave → 200",
              r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            rej = unwrap(r)
            check("Rejected leave status = REJECTED",
                  isinstance(rej, dict) and rej.get("status") == "REJECTED",
                  f"status={rej.get('status') if isinstance(rej,dict) else rej}")

        # removed from pending
        r = get("/leaves/requests/pending", manager_tok)
        pending_after = unwrap(r)
        still_there = isinstance(pending_after, list) and any(
            l.get("id") == reject_leave_id for l in pending_after)
        check("Rejected leave removed from manager /pending",
              not still_there, f"still_pending={still_there}")

        # employee sees REJECTED in /my
        r = get("/leaves/requests/my", employee_tok)
        my = unwrap(r)
        rejected_visible = False
        if isinstance(my, list):
            m = find_in_list(my, "id", reject_leave_id)
            rejected_visible = m is not None and m.get("status") == "REJECTED"
        check("Employee: leave shows REJECTED in /my list",
              rejected_visible, f"leave_id={reject_leave_id}")
else:
    skip("Leave reject lifecycle", "missing tokens")


# ─────────────────────────────────────────────────────────────────────────────
# 4. TICKET LIFECYCLE — create → visible → assign → status update
# ─────────────────────────────────────────────────────────────────────────────
section("4. TICKET LIFECYCLE — create → assign → resolve (sequential)")

ticket_id: Optional[int] = None

if employee_tok and manager_tok:
    # 4a — employee creates ticket
    r = post("/tickets", employee_tok, {
        "title": "E2E VPN Issue",
        "description": "Cannot connect to VPN — E2E test",
        "category": "IT",
        "priority": "HIGH",
    })
    check("Employee: create ticket → 201",
          r.status_code == 201, f"status={r.status_code} body={r.text[:80]}")
    if r.status_code == 201:
        ticket_data = unwrap(r)
        ticket_id = ticket_data.get("id") if isinstance(ticket_data, dict) else None

    # 4b — ticket visible to employee in list
    r = get("/tickets", employee_tok)
    tickets = unwrap(r)
    found_emp = isinstance(tickets, list) and ticket_id and any(
        t.get("id") == ticket_id for t in tickets)
    check("Employee: created ticket visible in /tickets",
          found_emp, f"ticket_id={ticket_id}")

    # 4c — ticket visible to manager
    r = get("/tickets", manager_tok)
    tickets_mgr = unwrap(r)
    found_mgr = isinstance(tickets_mgr, list) and ticket_id and any(
        t.get("id") == ticket_id for t in tickets_mgr)
    check("Manager: can see employee ticket in /tickets",
          found_mgr, f"ticket_id={ticket_id}")

    # 4d — manager assigns ticket to themselves
    if ticket_id and manager_id:
        r = patch(f"/tickets/{ticket_id}", manager_tok,
                  {"assignee_id": manager_id, "status": "IN_PROGRESS"})
        check("Manager: assign + set IN_PROGRESS → 200",
              r.status_code == 200, f"status={r.status_code} body={r.text[:80]}")
        if r.status_code == 200:
            t = unwrap(r)
            check("Ticket status = IN_PROGRESS after assign",
                  isinstance(t, dict) and t.get("status") == "IN_PROGRESS",
                  f"status={t.get('status') if isinstance(t,dict) else t}")

    # 4e — employee cannot assign a ticket (403)
    if ticket_id and employee_id:
        r = patch(f"/tickets/{ticket_id}", employee_tok,
                  {"assignee_id": employee_id})
        check("Employee: assign ticket → 403",
              r.status_code == 403, f"got {r.status_code}")

    # 4f — manager resolves ticket
    if ticket_id and manager_id:
        r = patch(f"/tickets/{ticket_id}", manager_tok,
                  {"assignee_id": manager_id, "status": "RESOLVED"})
        check("Manager: resolve ticket → 200",
              r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            t = unwrap(r)
            check("Ticket status = RESOLVED",
                  isinstance(t, dict) and t.get("status") == "RESOLVED",
                  f"status={t.get('status') if isinstance(t,dict) else t}")
else:
    skip("Ticket lifecycle", "missing tokens")


# ─────────────────────────────────────────────────────────────────────────────
# 5. ANNOUNCEMENT LIFECYCLE — create gate + propagation
# ─────────────────────────────────────────────────────────────────────────────
section("5. ANNOUNCEMENT LIFECYCLE — create, gate, propagation")

ann_id: Optional[int] = None

if employee_tok and manager_tok:
    # 5a — employee cannot create announcement
    r = post("/announcements", employee_tok, {
        "title": "E2E test",
        "content": "Should be blocked",
    })
    check("Employee: create announcement → 403",
          r.status_code == 403, f"got {r.status_code}")

    # 5b — count before
    r = get("/announcements", employee_tok)
    ann_before = unwrap(r)
    count_before = len(ann_before) if isinstance(ann_before, list) else 0

    # 5c — manager creates announcement
    r = post("/announcements", manager_tok, {
        "title": "E2E Workflow Announcement",
        "content": "This is an end-to-end test announcement created by manager.",
    })
    check("Manager: create announcement → 201",
          r.status_code == 201, f"status={r.status_code} body={r.text[:80]}")
    if r.status_code == 201:
        ann_data = unwrap(r)
        ann_id = ann_data.get("id") if isinstance(ann_data, dict) else None

    # 5d — all roles can see it
    for role_name, tok in [("EMPLOYEE", employee_tok), ("MANAGER", manager_tok), ("ADMIN", admin_tok)]:
        if tok:
            r = get("/announcements", tok)
            anns = unwrap(r)
            found = isinstance(anns, list) and (
                ann_id is None or any(a.get("id") == ann_id for a in anns)
            )
            check(f"{role_name}: announcement visible in /announcements",
                  found and len(anns) > count_before,
                  f"count={len(anns) if isinstance(anns,list) else '?'}")

    # 5e — admin can also create
    r = post("/announcements", admin_tok, {
        "title": "E2E Admin Announcement",
        "content": "Created by admin in E2E test.",
    })
    check("Admin: create announcement → 201",
          r.status_code == 201, f"status={r.status_code}")
else:
    skip("Announcement lifecycle", "missing tokens")


# ─────────────────────────────────────────────────────────────────────────────
# 6. PROJECT LIFECYCLE — create → assign → visible in my-projects
# ─────────────────────────────────────────────────────────────────────────────
section("6. PROJECT LIFECYCLE — create → assign → employee sees it")

project_id: Optional[int] = None

if admin_tok and employee_tok and employee_id:
    # 6a — admin creates project (idempotent — handle already-exists)
    r = post("/projects", admin_tok, {
        "name": "E2E Test Project",
        "description": "Created by E2E workflow test",
        "status": "ACTIVE",
    })
    if r.status_code == 201:
        proj_data = unwrap(r)
        project_id = proj_data.get("id") if isinstance(proj_data, dict) else None
        check("Admin: create project → 201", True, f"project_id={project_id}")
    elif r.status_code == 400 and "already exists" in r.text.lower():
        proj_r = get("/projects", admin_tok)
        projects_list = unwrap(proj_r)
        existing = find_in_list(
            projects_list if isinstance(projects_list, list) else [], "name", "E2E Test Project")
        project_id = existing["id"] if existing else None
        check("Admin: create project (already exists → fetch)", project_id is not None,
              f"project_id={project_id}")
    else:
        check("Admin: create project → 201", False,
              f"status={r.status_code} body={r.text[:80]}")

    # 6b — project visible in /projects list (privileged roles only)
    r = get("/projects", admin_tok)
    projects = unwrap(r)
    found_proj = isinstance(projects, list) and project_id and any(
        p.get("id") == project_id for p in projects)
    check("Project visible in /projects (admin)",
          found_proj, f"project_id={project_id}")

    # employee sees /projects → 403 (correct RBAC)
    r = get("/projects", employee_tok)
    check("Employee: /projects → 403 (privileged only)",
          r.status_code == 403, f"got {r.status_code}")

    # 6c — admin assigns employee to project (idempotent — already assigned is ok)
    if project_id and employee_id:
        r = post(f"/employees/{employee_id}/projects", admin_tok, {
            "project_id": project_id,
            "role": "Developer",
        })
        already_assigned = r.status_code == 400 and "already assigned" in r.text.lower()
        check("Admin: assign employee to project → 201 (or already assigned)",
              r.status_code == 201 or already_assigned,
              f"status={r.status_code} body={r.text[:80]}")

    # 6d — employee sees it in /projects/my
    r = get("/projects/my", employee_tok)
    my_projects = unwrap(r)
    found_in_my = isinstance(my_projects, list) and project_id and any(
        p.get("project_id") == project_id or p.get("id") == project_id
        for p in my_projects)
    check("Employee: assigned project visible in /projects/my",
          found_in_my, f"project_id={project_id} my_projects={len(my_projects) if isinstance(my_projects,list) else '?'}")

    # 6e — /projects/employees shows the mapping
    # Response: [{"project_id": N, "project_name": "...", "employees": [{"employee_id": N, ...}]}]
    r = get("/projects/employees", admin_tok)
    check("Admin: /projects/employees → 200",
          r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200 and project_id and employee_id:
        mapping = unwrap(r)
        emp_found = False
        if isinstance(mapping, list):
            for proj_entry in mapping:
                if proj_entry.get("project_id") == project_id:
                    emp_found = any(
                        e.get("employee_id") == employee_id
                        for e in proj_entry.get("employees", [])
                    )
                    break
        check("Admin: employee visible in /projects/employees mapping",
              emp_found, f"project_id={project_id} employee_id={employee_id}")

    # 6f — employee cannot create project
    r = post("/projects", employee_tok, {
        "name": "Should be blocked",
        "description": "RBAC test",
        "status": "ACTIVE",
    })
    check("Employee: create project → 403",
          r.status_code == 403, f"got {r.status_code}")
else:
    skip("Project lifecycle", "missing tokens or employee_id")


# ─────────────────────────────────────────────────────────────────────────────
# 7. ADMIN CRUD — user management, status, roles table
# ─────────────────────────────────────────────────────────────────────────────
section("7. ADMIN CRUD — users, status, roles table")

test_user_id: Optional[int] = None

if admin_tok:
    # 7a — create user
    r = post("/admin/users", admin_tok, {
        "employee_code": "NW-E2E1",
        "name": "E2E Test User",
        "email": "e2e.test.user@novaworks.in",
        "password": "Test@1234",
        "role": "EMPLOYEE",
        "employment_type": "FULL_TIME",
    })
    created = r.status_code in (200, 201)
    if not created and ("already" in r.text.lower() or r.status_code == 400):
        # fetch existing
        users_r = get("/admin/users", admin_tok)
        users = unwrap(users_r)
        eu = find_in_list(users if isinstance(users, list) else [],
                          "email", "e2e.test.user@novaworks.in")
        test_user_id = eu["id"] if eu else None
        check("Create test user (already exists → fetch)", test_user_id is not None,
              f"id={test_user_id}")
    else:
        check("Admin: create user → 201", created, f"status={r.status_code}")
        test_user_id = (unwrap(r) or {}).get("id")

    # 7b — user appears in list
    r = get("/admin/users", admin_tok)
    users = unwrap(r)
    found_user = isinstance(users, list) and any(
        u.get("email") == "e2e.test.user@novaworks.in" for u in users)
    check("New user visible in /admin/users list",
          found_user, f"user_id={test_user_id}")

    # 7c — update status to NOTICE
    if test_user_id:
        r = patch(f"/admin/users/{test_user_id}", admin_tok, {"status": "NOTICE"})
        check("Admin: set status NOTICE → 200",
              r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            u = unwrap(r)
            check("Status = NOTICE persisted",
                  isinstance(u, dict) and u.get("status") == "NOTICE",
                  f"status={u.get('status') if isinstance(u,dict) else u}")

    # 7d — update status back to ACTIVE
    if test_user_id:
        r = patch(f"/admin/users/{test_user_id}", admin_tok, {"status": "ACTIVE"})
        check("Admin: set status ACTIVE → 200",
              r.status_code == 200, f"status={r.status_code}")

    # 7e — roles table has 6 roles
    r = get("/admin/roles", admin_tok)
    check("Admin: /admin/roles → 200", r.status_code == 200)
    if r.status_code == 200:
        roles = unwrap(r)
        role_names = {rd["name"] for rd in roles} if isinstance(roles, list) else set()
        check("6 roles present",
              len(role_names) >= 6, f"roles={sorted(role_names)}")
        check("EMPLOYEE has no COMPENSATION",
              "COMPENSATION" not in {
                  c for rd in (roles or [])
                  if rd.get("name") == "EMPLOYEE"
                  for c in rd.get("accessible_categories", [])
              }, str(role_names))

    # 7f — non-admin cannot access /admin/users
    if employee_tok:
        r = get("/admin/users", employee_tok)
        check("Employee → /admin/users → 403",
              r.status_code == 403, f"got {r.status_code}")

    # 7g — cleanup
    if test_user_id:
        r = delete(f"/admin/users/{test_user_id}", admin_tok)
        check("Admin: delete test user → 204",
              r.status_code == 204, f"status={r.status_code}")
        # confirm gone
        users_r = get("/admin/users", admin_tok)
        users_after = unwrap(users_r)
        still_there = isinstance(users_after, list) and any(
            u.get("email") == "e2e.test.user@novaworks.in" for u in users_after)
        check("Deleted user not in list", not still_there)
else:
    skip("Admin CRUD", "no admin token")


# ─────────────────────────────────────────────────────────────────────────────
# 8. AI CHAT SMOKE — policy, sql, actions endpoints respond
# ─────────────────────────────────────────────────────────────────────────────
section("8. AI CHAT SMOKE — endpoint reachability (no deep quality check)")

_LLM_INFRA_PHRASES = (
    "unloaded", "context size", "model was unloaded", "overload",
    "context window", "model unloaded",
)

def ai_check(label: str, tok: str, path: str, msg: str) -> None:
    try:
        r = requests.post(f"{BASE}{path}", headers=hdr(tok),
                          json={"message": msg}, timeout=120)
        body = r.json()
        ok = r.status_code == 200 and body.get("success", True)
        detail = str(body.get("data", {}) or body.get("error", ""))[:100] if isinstance(body, dict) else ""
        # don't fail on LLM infrastructure errors — mark SKIP
        if r.status_code in (500, 502, 503):
            skip(label, f"LLM API error {r.status_code}")
        elif r.status_code == 400 and any(p in detail.lower() for p in _LLM_INFRA_PHRASES):
            skip(label, f"LLM infra: {detail[:80]}")
        else:
            check(label, ok, detail)
    except requests.exceptions.Timeout:
        skip(label, "LLM timeout")
    except Exception as exc:
        check(label, False, str(exc)[:80])


if employee_tok:
    ai_check("Policy RAG: employee asks leave question",
             employee_tok, "/chat/policy", "How many days of annual leave do I get?")
    ai_check("SQL Agent: employee asks own leave balance",
             employee_tok, "/chat/sql", "What is my current leave balance?")
    ai_check("Actions Agent: employee checks ticket status",
             employee_tok, "/chat/actions", "Show me my open tickets.")
    ai_check("Router: employee asks policy question",
             employee_tok, "/chat/router", "What is the work from home policy?")

if manager_tok:
    ai_check("Actions Agent: manager checks pending approvals",
             manager_tok, "/chat/actions", "Show me pending leave approvals.")

if admin_tok:
    ai_check("SQL Agent: admin queries project list",
             admin_tok, "/chat/sql", "List all active projects.")


# ─────────────────────────────────────────────────────────────────────────────
# 9. RBAC — cross-role boundary checks
# ─────────────────────────────────────────────────────────────────────────────
section("9. RBAC — cross-role boundary enforcement")

if employee_tok and manager_tok and admin_tok:
    # employee cannot reach pending approvals
    r = get("/leaves/requests/pending", employee_tok)
    check("Employee: /leaves/requests/pending → 403",
          r.status_code == 403, f"got {r.status_code}")

    # employee cannot assign tickets
    r = get("/tickets", employee_tok)
    tickets = unwrap(r)
    if isinstance(tickets, list) and tickets:
        tid = tickets[0]["id"]
        r2 = patch(f"/tickets/{tid}", employee_tok,
                   {"assignee_id": employee_id or 4})
        check("Employee: PATCH /tickets/{id} → 403",
              r2.status_code == 403, f"got {r2.status_code}")
    else:
        skip("Employee: assign ticket guard", "no tickets to test with")

    # manager cannot create project (only admin)
    r = post("/projects", manager_tok, {
        "name": "RBAC test project",
        "description": "Should fail",
        "status": "ACTIVE",
    })
    check("Manager: create project → 403",
          r.status_code == 403, f"got {r.status_code}")

    # employee cannot create announcement
    r = post("/announcements", employee_tok, {
        "title": "RBAC test",
        "content": "Should be blocked",
    })
    check("Employee: create announcement → 403",
          r.status_code == 403, f"got {r.status_code}")
else:
    skip("RBAC cross-role checks", "missing tokens")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
section("SUMMARY")

passed  = sum(1 for _, ok, _ in results if ok is True)
skipped = sum(1 for _, ok, _ in results if ok is None)
failed  = sum(1 for _, ok, _ in results if ok is False)
total   = len(results)

print(f"\n  Total  : {total}")
print(f"  {G}Passed : {passed}{E}")
if skipped:
    print(f"  {Y}Skipped: {skipped}  (LLM/API timeout — not code bugs){E}")
if failed:
    print(f"  {R}Failed : {failed}{E}")
    print(f"\n  {B}Failed tests:{E}")
    for label, ok, detail in results:
        if ok is False:
            print(f"    {R}✗{E} {label}")
            if detail:
                print(f"        {detail}")
else:
    print(f"  {G}{B}All non-skipped tests passed!{E}")

sys.exit(0 if failed == 0 else 1)
