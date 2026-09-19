from classroom.ids import CODE_ALPHABET

from classroom_helpers import auth, capp, signup  # noqa: F401


def setup_class(capp):
    t = signup(capp, "prof@demo.edu", "teacher")
    klass = capp.post("/api/classes", json={"name": "Writing 101"}, headers=auth(t["token"])).json()
    return t, klass


def test_create_class_code_and_teacher_membership(capp):
    t, klass = setup_class(capp)
    assert len(klass["class_code"]) == 6 and all(ch in CODE_ALPHABET for ch in klass["class_code"])
    assert klass["teacher_name"] == "Prof" and klass["student_count"] == 0
    assert capp.post("/api/classes", json={"name": "x"}, headers=auth(signup(capp, "s@demo.edu")["token"])).status_code == 403


def test_join_by_code_is_case_insensitive_and_idempotent(capp):
    t, klass = setup_class(capp)
    s = signup(capp, "ana@demo.edu")
    r = capp.post("/api/classes/join", json={"class_code": klass["class_code"].lower()}, headers=auth(s["token"]))
    assert r.status_code == 200 and r.json()["name"] == "Writing 101" and r.json()["class_code"] is None
    assert capp.post("/api/classes/join", json={"class_code": klass["class_code"]}, headers=auth(s["token"])).status_code == 200
    assert capp.post("/api/classes/join", json={"class_code": "NOPE22"}, headers=auth(s["token"])).status_code == 404
    assert capp.post("/api/classes/join", json={"class_code": klass["class_code"]}, headers=auth(t["token"])).status_code == 403

    mine = capp.get("/api/classes", headers=auth(s["token"])).json()
    assert [c["class_id"] for c in mine] == [klass["class_id"]]
    assert capp.get("/api/classes", headers=auth(t["token"])).json()[0]["student_count"] == 1


def test_signup_with_class_code_joins(capp):
    _, klass = setup_class(capp)
    s = signup(capp, "ben@demo.edu", class_code=klass["class_code"].lower())
    assert capp.get("/api/classes", headers=auth(s["token"])).json()[0]["class_id"] == klass["class_id"]


def test_class_detail_visibility(capp):
    t, klass = setup_class(capp)
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    outsider = signup(capp, "out@demo.edu")
    other_teacher = signup(capp, "other@demo.edu", "teacher")

    d = capp.get(f"/api/classes/{klass['class_id']}", headers=auth(t["token"])).json()
    assert d["class"]["class_code"] == klass["class_code"] and [r["email"] for r in d["roster"]] == ["ana@demo.edu"]
    d = capp.get(f"/api/classes/{klass['class_id']}", headers=auth(s["token"])).json()
    assert d["class"]["class_code"] is None and "roster" not in d
    assert capp.get(f"/api/classes/{klass['class_id']}", headers=auth(outsider["token"])).status_code == 404
    assert capp.get(f"/api/classes/{klass['class_id']}", headers=auth(other_teacher["token"])).status_code == 404


def test_regenerate_code(capp):
    t, klass = setup_class(capp)
    new = capp.post(f"/api/classes/{klass['class_id']}/regenerate-code", headers=auth(t["token"])).json()["class_code"]
    assert new != klass["class_code"]
    s = signup(capp, "ana@demo.edu")
    assert capp.post("/api/classes/join", json={"class_code": klass["class_code"]}, headers=auth(s["token"])).status_code == 404
    assert capp.post("/api/classes/join", json={"class_code": new}, headers=auth(s["token"])).status_code == 200


def test_assignment_lifecycle(capp):
    t, klass = setup_class(capp)
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    body = {"class_id": klass["class_id"], "title": "Position paper", "instructions": "Argue a position.",
            "points": 50, "published": False, "settings": {"factcheck": True, "similarity": False}}
    a = capp.post("/api/assignments", json=body, headers=auth(t["token"]))
    assert a.status_code == 201
    a = a.json()
    assert a["settings"]["similarity"] is False and a["settings"]["allow_paste"] is True
    assert a["submission_counts"] == {"draft": 0, "submitted": 0, "graded": 0, "returned": 0}

    # Unpublished: invisible to students, visible to the owning teacher.
    assert capp.get(f"/api/assignments/{a['assignment_id']}", headers=auth(s["token"])).status_code == 404
    assert capp.get(f"/api/classes/{klass['class_id']}", headers=auth(s["token"])).json()["assignments"] == []
    assert capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).status_code == 404

    r = capp.put(f"/api/assignments/{a['assignment_id']}", json={"published": True, "points": 60}, headers=auth(t["token"]))
    assert r.status_code == 200 and r.json()["published"] is True and r.json()["points"] == 60
    got = capp.get(f"/api/assignments/{a['assignment_id']}", headers=auth(s["token"])).json()
    assert got["title"] == "Position paper" and got["my_submission"] is None

    other = signup(capp, "other@demo.edu", "teacher")
    assert capp.post("/api/assignments", json=body, headers=auth(other["token"])).status_code == 404
    assert capp.put(f"/api/assignments/{a['assignment_id']}", json={"title": "x"}, headers=auth(other["token"])).status_code == 404


def test_start_draft_and_grading_flow(capp):
    t, klass = setup_class(capp)
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    lurker = signup(capp, "ben@demo.edu", class_code=klass["class_code"])
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "Essay"}, headers=auth(t["token"])).json()

    d1 = capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).json()
    d2 = capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).json()
    assert d1["submission_id"] == d2["submission_id"] and d1["status"] == "draft"
    assert d1["assignment"]["title"] == "Essay" and d1["student_name"] == "Ana"

    sid = d1["submission_id"]
    assert capp.put(f"/api/submissions/{sid}/draft", json={"content": "hello"}, headers=auth(s["token"])).status_code == 200
    assert capp.get(f"/api/submissions/{sid}", headers=auth(s["token"])).json()["content"] == "hello"
    assert capp.get(f"/api/submissions/{sid}", headers=auth(t["token"])).status_code == 200
    assert capp.get(f"/api/submissions/{sid}", headers=auth(lurker["token"])).status_code == 404
    assert capp.put(f"/api/submissions/{sid}/draft", json={"content": "x"}, headers=auth(lurker["token"])).status_code == 404

    # Teacher table lists every enrolled student, started or not.
    table = capp.get(f"/api/assignments/{a['assignment_id']}/submissions", headers=auth(t["token"])).json()
    assert [(r["student"]["name"], r["status"]) for r in table] == [("Ana", "draft"), ("Ben", "not_started")]

    # Cannot grade a draft; once submitted (simulated here — Stage 3 owns the real path) grading + return work.
    assert capp.post(f"/api/submissions/{sid}/grade", json={"grade": 40}, headers=auth(t["token"])).status_code == 409
    capp.app.state.db.exec("UPDATE submissions SET status='submitted', submitted_ms=1 WHERE submission_id=?", (sid,))
    assert capp.post(f"/api/submissions/{sid}/grade", json={"grade": 400}, headers=auth(t["token"])).status_code == 422
    g = capp.post(f"/api/submissions/{sid}/grade", json={"grade": 88.5, "feedback": "Strong thesis."}, headers=auth(t["token"]))
    assert g.status_code == 200 and g.json()["status"] == "graded" and g.json()["grade"] == 88.5
    assert capp.post(f"/api/submissions/{sid}/return", headers=auth(t["token"])).json()["status"] == "returned"
    assert capp.put(f"/api/submissions/{sid}/draft", json={"content": "late edit"}, headers=auth(s["token"])).status_code == 409

    mine = capp.get(f"/api/assignments/{a['assignment_id']}", headers=auth(s["token"])).json()["my_submission"]
    assert mine["status"] == "returned" and mine["grade"] == 88.5


def test_dashboards(capp):
    t, klass = setup_class(capp)
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "Essay", "due_ms": 1_800_000_000_000},
                  headers=auth(t["token"])).json()

    sd = capp.get("/api/dashboard", headers=auth(s["token"])).json()
    assert sd["role"] == "student" and sd["classes"][0]["name"] == "Writing 101"
    assert sd["due_soon"][0]["title"] == "Essay" and sd["due_soon"][0]["status"] == "not_started"

    td = capp.get("/api/dashboard", headers=auth(t["token"])).json()
    assert td["role"] == "teacher" and td["tiles"] == {"classes": 1, "students": 1, "assignments": 1, "to_grade": 0}
    assert td["classes"][0]["class_code"] == klass["class_code"] and td["recent"] == []

    sid = capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).json()["submission_id"]
    capp.app.state.db.exec("UPDATE submissions SET status='submitted', submitted_ms=5 WHERE submission_id=?", (sid,))
    td = capp.get("/api/dashboard", headers=auth(t["token"])).json()
    assert td["tiles"]["to_grade"] == 1 and td["recent"][0]["student_name"] == "Ana"
    assert capp.get("/api/dashboard", headers=auth(s["token"])).json()["due_soon"] == []
