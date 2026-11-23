"""Paid birth-time rectification tasks, reports and privacy-safe deletion jobs."""
import json
import secrets
import time

from fastapi import HTTPException

STATUSES = ("draft", "submitted", "processing", "completed", "failed", "expired")
DELETION_STATES = ("retained", "pending", "deleted", "failed")
PRIVACY_VERSION = "2026-11-17-rectification-processing-v2"
STAGES = 6
MAX_DRAFT_BYTES = 96 * 1024
ALLOWED_SECTIONS = {f"stage{i}" for i in range(1, STAGES + 1)}
REQUIRED_FIELDS = {
    "stage1": ("birthDate", "birthPlace", "knownTime", "timeSource", "errorRange"),
    "stage2": ("bodyBuild", "facialFeatures", "physicalMarks"),
    "stage3": ("personality", "familyBackground", "migration"),
}


def initialize(store):
    with store.connect() as db:
        db.executescript(
            """CREATE TABLE IF NOT EXISTS rectification_tasks(
id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,order_id TEXT NOT NULL UNIQUE,
status TEXT NOT NULL CHECK(status IN ('draft','submitted','processing','completed','failed','expired')),
current_stage INTEGER NOT NULL DEFAULT 1 CHECK(current_stage BETWEEN 1 AND 6),
progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
privacy_version TEXT,privacy_accepted_at REAL,submitted_at REAL,report_id TEXT,
deletion_status TEXT NOT NULL DEFAULT 'retained' CHECK(deletion_status IN ('retained','pending','deleted','failed')),
deleted_at REAL,created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rectification_drafts(
task_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,data_json TEXT NOT NULL,
revision INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rectification_runs(
task_id TEXT PRIMARY KEY,run_id TEXT NOT NULL UNIQUE,state TEXT NOT NULL,
attempts INTEGER NOT NULL DEFAULT 0,input_revision INTEGER,started REAL,finished REAL,
error_code TEXT,error_detail TEXT,provider_policy_ack TEXT,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rectification_reports(
id TEXT PRIMARY KEY,task_id TEXT NOT NULL UNIQUE,owner_id TEXT NOT NULL,
report_text TEXT NOT NULL,interval_start TEXT NOT NULL,interval_end TEXT NOT NULL,
reference_time TEXT NOT NULL,d1_json TEXT NOT NULL,d9_json TEXT NOT NULL,
support_level TEXT NOT NULL,limitations TEXT NOT NULL,prompt_version TEXT NOT NULL,
created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rectification_deletions(
task_id TEXT PRIMARY KEY,status TEXT NOT NULL,requested REAL NOT NULL,started REAL,
completed REAL,result_json TEXT,error_code TEXT,updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS rectification_owner_updated ON rectification_tasks(owner_id,updated DESC);
CREATE INDEX IF NOT EXISTS rectification_draft_owner ON rectification_drafts(owner_id,updated DESC);
CREATE INDEX IF NOT EXISTS rectification_status ON rectification_tasks(status,updated DESC);
CREATE INDEX IF NOT EXISTS rectification_report_owner ON rectification_reports(owner_id,updated DESC);
CREATE INDEX IF NOT EXISTS rectification_deletion_status ON rectification_deletions(status,updated DESC);
INSERT OR IGNORE INTO schema_version VALUES (7);"""
        )


def _task_row(db, owner, task_id=None):
    select = """SELECT id,order_id,status,current_stage,progress,privacy_version,
privacy_accepted_at,submitted_at,report_id,deletion_status,created,updated
FROM rectification_tasks"""
    if task_id:
        return db.execute(select + " WHERE id=? AND owner_id=?", (task_id, owner)).fetchone()
    return db.execute(select + " WHERE owner_id=? ORDER BY updated DESC LIMIT 1", (owner,)).fetchone()


def _as_task(row):
    if not row:
        return None
    keys = ("id", "orderId", "status", "currentStage", "progress", "privacyVersion", "privacyAcceptedAt", "submittedAt", "reportId", "deletionStatus", "created", "updated")
    return dict(zip(keys, row))


def _paid_order(db, owner, order_id=None):
    params = [owner, "rectification", "paid"]
    where = "owner=? AND product=? AND status=?"
    if order_id:
        where += " AND id=?"
        params.append(order_id)
    where += " AND NOT EXISTS(SELECT 1 FROM rectification_tasks t WHERE t.order_id=payment_orders.id)"
    return db.execute("SELECT id,paid_at FROM payment_orders WHERE " + where + " ORDER BY paid_at DESC LIMIT 1", params).fetchone()


def current(store, owner):
    with store.connect() as db:
        row = _task_row(db, owner)
        task = _as_task(row)
        if task:
            draft = db.execute("SELECT data_json,revision,updated FROM rectification_drafts WHERE task_id=? AND owner_id=?", (task["id"], owner)).fetchone()
            task["draft"] = json.loads(draft[0]) if draft else {}
            task["revision"] = draft[1] if draft else 0
            task["lastSavedAt"] = draft[2] if draft else task["updated"]
            if task["reportId"]:
                report_row = db.execute("SELECT interval_start,interval_end,reference_time,support_level,created FROM rectification_reports WHERE id=? AND owner_id=?", (task["reportId"], owner)).fetchone()
                if report_row:
                    task["result"] = dict(zip(("intervalStart", "intervalEnd", "referenceTime", "supportLevel", "created"), report_row))
        available = _paid_order(db, owner)
    return {"task": task, "availableOrderId": available[0] if available else None, "canStart": bool(task or available)}


def start(store, owner, order_id=None):
    now = time.time()
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = _task_row(db, owner)
        if existing and existing[2] not in ("completed", "expired"):
            return _as_task(existing)
        paid = _paid_order(db, owner, order_id)
        if not paid:
            raise HTTPException(402, "请先完成出生时间校准服务付款")
        task_id = secrets.token_urlsafe(24)
        db.execute("INSERT INTO rectification_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (task_id, owner, paid[0], "draft", 1, 0, None, None, None, None, "retained", None, now, now))
        db.execute("INSERT INTO rectification_drafts VALUES (?,?,?,?,?,?)", (task_id, owner, "{}", 1, now, now))
    return _as_task((task_id, paid[0], "draft", 1, 0, None, None, None, None, "retained", now, now))


def accept_privacy(store, owner, task_id, accepted):
    if accepted is not True:
        raise HTTPException(422, "请主动确认隐私声明后继续")
    now = time.time()
    with store.connect() as db:
        if db.execute("UPDATE rectification_tasks SET privacy_version=?,privacy_accepted_at=?,updated=? WHERE id=? AND owner_id=? AND status='draft'", (PRIVACY_VERSION, now, now, task_id, owner)).rowcount != 1:
            raise HTTPException(404, "校准任务不存在或当前状态不可修改")
    return {"accepted": True, "privacyVersion": PRIVACY_VERSION, "acceptedAt": now}


def _clean(value, depth=0):
    if depth > 5:
        raise HTTPException(422, "资料结构过深")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.strip()[:4000]
    if isinstance(value, list):
        return [_clean(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key)[:60]: _clean(item, depth + 1) for key, item in list(value.items())[:80]}
    raise HTTPException(422, "资料包含不支持的格式")


def sanitize(data):
    if not isinstance(data, dict) or set(data) - ALLOWED_SECTIONS:
        raise HTTPException(422, "问卷资料结构无效")
    clean = _clean(data)
    raw = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
    if len(raw.encode()) > MAX_DRAFT_BYTES:
        raise HTTPException(413, "草稿内容过大，请精简后保存")
    return clean, raw


def save_draft(store, owner, task_id, current_stage, data):
    if not 1 <= current_stage <= STAGES:
        raise HTTPException(422, "问卷阶段无效")
    clean, raw = sanitize(data)
    now = time.time()
    progress = min(95, round((current_stage - 1) / STAGES * 100))
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        task = _task_row(db, owner, task_id)
        if not task:
            raise HTTPException(404, "校准任务不存在")
        if task[2] != "draft":
            raise HTTPException(409, "资料已经提交，不能继续修改")
        if not task[6]:
            raise HTTPException(428, "请先确认出生时间校准隐私声明")
        db.execute("""INSERT INTO rectification_drafts(task_id,owner_id,data_json,revision,created,updated)
VALUES (?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET data_json=excluded.data_json,
revision=rectification_drafts.revision+1,updated=excluded.updated WHERE rectification_drafts.owner_id=excluded.owner_id""", (task_id, owner, raw, 1, now, now))
        db.execute("UPDATE rectification_tasks SET current_stage=?,progress=?,updated=? WHERE id=? AND owner_id=?", (current_stage, progress, now, task_id, owner))
        revision = db.execute("SELECT revision FROM rectification_drafts WHERE task_id=? AND owner_id=?", (task_id, owner)).fetchone()[0]
    return {"saved": True, "taskId": task_id, "currentStage": current_stage, "progress": progress, "revision": revision, "savedAt": now, "data": clean}


def _validate_submission(data):
    required = {f"stage{i}" for i in range(1, 6)}
    if not required.issubset(data):
        raise HTTPException(422, "请先完成前五个资料阶段")
    for section, fields in REQUIRED_FIELDS.items():
        if not isinstance(data.get(section), dict) or any(not data[section].get(field) for field in fields):
            raise HTTPException(422, "前五个资料阶段存在未完成的必填内容")
    relationship = data.get("stage4", {})
    if not isinstance(relationship, dict):
        raise HTTPException(422, "恋爱及婚姻关系资料结构无效")
    if not relationship.get("skipRelationship") and any(not relationship.get(field) for field in ("partnerProfile", "partnerRole", "relationshipTimeline")):
        raise HTTPException(422, "请完整填写关系信息，或选择跳过该阶段")
    events = data.get("stage5", {}).get("events", [])
    valid = [event for event in events if isinstance(event, dict) and event.get("category") and event.get("month") and event.get("description") and event.get("impact")]
    if len(valid) < 3:
        raise HTTPException(422, "请至少填写3个时间明确的人生重大事件")


def task_draft(store, owner, task_id):
    with store.connect() as db:
        task = _task_row(db, owner, task_id)
        if not task:
            raise HTTPException(404, "校准任务不存在")
        row = db.execute("SELECT data_json,revision FROM rectification_drafts WHERE task_id=? AND owner_id=?", (task_id, owner)).fetchone()
    return (json.loads(row[0]), row[1]) if row else ({}, 0)


def submit(store, owner, task_id):
    now = time.time()
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        task = _task_row(db, owner, task_id)
        if not task:
            raise HTTPException(404, "校准任务不存在")
        if task[2] in ("submitted", "processing", "completed"):
            return {"submitted": True, "taskId": task_id, "status": task[2], "progress": task[4], "duplicate": True}
        if task[2] != "draft":
            raise HTTPException(409, "任务失败后请使用重新处理入口，不需要再次购买")
        if not task[6]:
            raise HTTPException(428, "请先确认隐私声明")
        draft = db.execute("SELECT data_json FROM rectification_drafts WHERE task_id=? AND owner_id=?", (task_id, owner)).fetchone()
        data = json.loads(draft[0]) if draft else {}
        _validate_submission(data)
        db.execute("UPDATE rectification_tasks SET status='submitted',current_stage=6,progress=100,submitted_at=?,updated=? WHERE id=? AND owner_id=?", (now, now, task_id, owner))
    return {"submitted": True, "taskId": task_id, "status": "submitted", "progress": 100, "submittedAt": now, "shouldSchedule": True}


def retry(store, owner, task_id):
    now = time.time()
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        task = _task_row(db, owner, task_id)
        if not task:
            raise HTTPException(404, "校准任务不存在")
        if task[2] == "completed":
            return {"taskId": task_id, "status": "completed", "duplicate": True}
        if task[2] not in ("failed", "submitted"):
            raise HTTPException(409, "当前任务不能重新处理")
        if not db.execute("SELECT 1 FROM rectification_drafts WHERE task_id=? AND owner_id=?", (task_id, owner)).fetchone():
            raise HTTPException(409, "原始资料不存在，无法重新处理")
        db.execute("UPDATE rectification_tasks SET status='submitted',deletion_status='retained',updated=? WHERE id=? AND owner_id=?", (now, task_id, owner))
    return {"taskId": task_id, "status": "submitted", "shouldSchedule": True}


def claim(store, task_id, provider_policy_ack):
    now = time.time()
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT t.owner_id,t.order_id,d.data_json,d.revision
FROM rectification_tasks t JOIN rectification_drafts d ON d.task_id=t.id AND d.owner_id=t.owner_id
JOIN payment_orders p ON p.id=t.order_id AND p.owner=t.owner_id
WHERE t.id=? AND t.status='submitted' AND p.product='rectification' AND p.status='paid'""", (task_id,)).fetchone()
        if not row:
            return None
        prior = db.execute("SELECT attempts FROM rectification_runs WHERE task_id=?", (task_id,)).fetchone()
        run_id = secrets.token_urlsafe(24)
        attempts = (prior[0] if prior else 0) + 1
        db.execute("""INSERT INTO rectification_runs(task_id,run_id,state,attempts,input_revision,started,finished,error_code,error_detail,provider_policy_ack,updated)
VALUES (?,?,?,?,?,?,NULL,NULL,NULL,?,?) ON CONFLICT(task_id) DO UPDATE SET run_id=excluded.run_id,state='processing',attempts=excluded.attempts,input_revision=excluded.input_revision,started=excluded.started,finished=NULL,error_code=NULL,error_detail=NULL,provider_policy_ack=excluded.provider_policy_ack,updated=excluded.updated""", (task_id, run_id, "processing", attempts, row[3], now, provider_policy_ack, now))
        db.execute("UPDATE rectification_tasks SET status='processing',updated=? WHERE id=? AND status='submitted'", (now, task_id))
    return {"taskId": task_id, "owner": row[0], "orderId": row[1], "data": json.loads(row[2]), "revision": row[3], "runId": run_id}


def complete(store, task_id, run_id, result, prompt_version):
    now = time.time()
    report_id = secrets.token_urlsafe(24)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT owner_id,status FROM rectification_tasks WHERE id=?", (task_id,)).fetchone()
        run = db.execute("SELECT state,run_id FROM rectification_runs WHERE task_id=?", (task_id,)).fetchone()
        if not row or row[1] != "processing" or not run or run != ("processing", run_id):
            return False
        db.execute("INSERT INTO rectification_reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            report_id, task_id, row[0], result["report"], result["intervalStart"], result["intervalEnd"], result["referenceTime"],
            json.dumps(result["d1"], ensure_ascii=False), json.dumps(result["d9"], ensure_ascii=False), result["supportLevel"], result["limitations"], prompt_version, now, now,
        ))
        saved = db.execute("SELECT 1 FROM rectification_reports WHERE id=? AND task_id=? AND length(report_text)>0", (report_id, task_id)).fetchone()
        if not saved:
            raise RuntimeError("报告保存确认失败")
        db.execute("UPDATE rectification_tasks SET status='completed',report_id=?,deletion_status='pending',updated=? WHERE id=?", (report_id, now, task_id))
        db.execute("UPDATE rectification_runs SET state='completed',finished=?,updated=? WHERE task_id=? AND run_id=?", (now, now, task_id, run_id))
        db.execute("INSERT INTO rectification_deletions VALUES (?,?,?,?,?,?,?,?)", (task_id, "pending", now, None, None, None, None, now))
    return True


def delete_private_data(store, task_id):
    now = time.time()
    try:
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT status,report_id FROM rectification_tasks WHERE id=?", (task_id,)).fetchone()
            if not task or task[0] != "completed" or not task[1]:
                raise RuntimeError("任务或报告状态不满足删除条件")
            if not db.execute("SELECT 1 FROM rectification_reports WHERE id=? AND task_id=? AND length(report_text)>0 AND length(reference_time)>0", (task[1], task_id)).fetchone():
                raise RuntimeError("报告或最终时间保存确认失败")
            db.execute("UPDATE rectification_deletions SET status='processing',started=?,updated=? WHERE task_id=?", (now, now, task_id))
            removed = db.execute("DELETE FROM rectification_drafts WHERE task_id=?", (task_id,)).rowcount
            result = json.dumps({"databaseDraftRows": removed, "cacheEntries": 0, "temporaryFiles": 0, "thirdPartyDeletion": "provider-policy-separate"}, separators=(",", ":"))
            finished = time.time()
            db.execute("UPDATE rectification_deletions SET status='completed',completed=?,result_json=?,error_code=NULL,updated=? WHERE task_id=?", (finished, result, finished, task_id))
            db.execute("UPDATE rectification_tasks SET deletion_status='deleted',deleted_at=?,updated=? WHERE id=?", (finished, finished, task_id))
        return True
    except Exception:
        with store.connect() as db:
            db.execute("UPDATE rectification_deletions SET status='failed',error_code='LOCAL_DELETE_FAILED',updated=? WHERE task_id=?", (time.time(), task_id))
            db.execute("UPDATE rectification_tasks SET deletion_status='failed',updated=? WHERE id=?", (time.time(), task_id))
        return False


def fail(store, task_id, run_id, code, detail=""):
    now = time.time()
    safe = str(detail).replace("\n", " ")[:300]
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE rectification_runs SET state='failed',finished=?,error_code=?,error_detail=?,updated=? WHERE task_id=? AND run_id=? AND state='processing'", (now, code[:60], safe, now, task_id, run_id))
        db.execute("UPDATE rectification_tasks SET status='failed',deletion_status='retained',updated=? WHERE id=? AND status='processing'", (now, task_id))


def recover_interrupted(store):
    now = time.time()
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        interrupted = [row[0] for row in db.execute("SELECT id FROM rectification_tasks WHERE status='processing'").fetchall()]
        for task_id in interrupted:
            db.execute("UPDATE rectification_tasks SET status='failed',deletion_status='retained',updated=? WHERE id=?", (now, task_id))
            db.execute("UPDATE rectification_runs SET state='failed',finished=?,error_code='PROCESS_INTERRUPTED',error_detail='服务重启，原始资料已保留，可安全重试',updated=? WHERE task_id=?", (now, now, task_id))
        submitted = [row[0] for row in db.execute("SELECT id FROM rectification_tasks WHERE status='submitted'").fetchall()]
    return submitted


def pending_deletions(store):
    with store.connect() as db:
        return [row[0] for row in db.execute("""SELECT t.id FROM rectification_tasks t
JOIN rectification_reports r ON r.task_id=t.id
WHERE t.status='completed' AND t.deletion_status IN ('pending','failed')""").fetchall()]


def report(store, owner, task_id):
    with store.connect() as db:
        row = db.execute("""SELECT r.id,r.report_text,r.interval_start,r.interval_end,r.reference_time,
r.d1_json,r.d9_json,r.support_level,r.limitations,r.prompt_version,r.created,t.deletion_status
FROM rectification_reports r JOIN rectification_tasks t ON t.id=r.task_id
WHERE r.task_id=? AND r.owner_id=? AND t.owner_id=? AND t.status='completed'""", (task_id, owner, owner)).fetchone()
    if not row:
        raise HTTPException(404, "校准报告不存在或尚未完成")
    keys = ("id", "text", "intervalStart", "intervalEnd", "referenceTime", "d1", "d9", "supportLevel", "limitations", "promptVersion", "created", "deletionStatus")
    result = dict(zip(keys, row))
    result["d1"] = json.loads(result["d1"])
    result["d9"] = json.loads(result["d9"])
    return result


def schema_info():
    return {"version": 2, "statuses": STATUSES, "deletionStates": DELETION_STATES, "privacyVersion": PRIVACY_VERSION, "stages": STAGES, "automaticDeletionEnabled": True}
