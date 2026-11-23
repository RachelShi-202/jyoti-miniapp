"""Dependency-light smoke test for the rectification draft boundary."""
import json
import sqlite3
import sys
import tempfile
import types


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


fastapi = types.ModuleType("fastapi")
fastapi.HTTPException = HTTPException
sys.modules["fastapi"] = fastapi
sys.path.insert(0, "web")
import rectification  # noqa: E402
from rectification_engine import build_analysis, candidate_times, parse_model_result, supplemental_questions  # noqa: E402


class Store:
    def __init__(self, path):
        self.path = path

    def connect(self):
        return sqlite3.connect(self.path)


def main():
    with tempfile.TemporaryDirectory(dir="web/tests") as directory:
        store = Store(directory + "/rectification.sqlite3")
        with store.connect() as db:
            db.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY)")
            db.execute("CREATE TABLE payment_orders(id TEXT PRIMARY KEY,owner TEXT,product TEXT,status TEXT,paid_at REAL)")
            db.executemany(
                "INSERT INTO payment_orders VALUES (?,?,?,?,?)",
                [("paid-a", "alice", "rectification", "paid", 1), ("paid-b", "bob", "rectification", "paid", 2)],
            )
        rectification.initialize(store)
        alice = rectification.start(store, "alice", "paid-a")
        assert rectification.current(store, "bob")["task"] is None
        try:
            rectification.start(store, "bob", "paid-a")
            raise AssertionError("cross-account order was accepted")
        except HTTPException as error:
            assert error.status_code == 402
        rectification.accept_privacy(store, "alice", alice["id"], True)
        data = {
            "stage1": {"birthDate": "2000-01-01", "birthPlace": "上海", "knownTime": "上午", "timeSource": "家人回忆", "errorRange": "1小时"},
            "stage2": {"bodyBuild": "中等", "facialFeatures": "描述", "physicalMarks": "无"},
            "stage3": {"personality": "描述", "familyBackground": "描述", "migration": "描述"},
            "stage4": {"skipRelationship": True},
            "stage5": {},
            "stage6": {},
        }
        data["stage5"] = {
            "events": [
                {"category": "学业", "month": "2018-09", "description": "入学", "impact": "重要"},
                {"category": "事业", "month": "2022-07", "description": "工作", "impact": "重大"},
                {"category": "家庭", "month": "2024-01", "description": "迁居", "impact": "重要"},
            ]
        }
        saved = rectification.save_draft(store, "alice", alice["id"], 6, data)
        assert saved["revision"] == 2
        restored = rectification.current(store, "alice")["task"]
        assert restored["draft"]["stage5"]["events"][1]["category"] == "事业"
        assert restored["revision"] == 2 and restored["currentStage"] == 6 and restored["lastSavedAt"] >= saved["savedAt"]
        submitted = rectification.submit(store, "alice", alice["id"])
        assert submitted["status"] == "submitted"
        assert rectification.submit(store, "alice", alice["id"])["duplicate"] is True
        claimed = rectification.claim(store, alice["id"], "contract-reviewed-2026-11-17")
        assert claimed and claimed["revision"] == 2
        assert rectification.claim(store, alice["id"], "contract-reviewed-2026-11-17") is None
        result = {
            "report": "## 01｜出生时间校准结论\n中等支持。\n## 02｜D1本命盘验证\n已核验。\n## 03｜D9九分盘验证\n已核验。\n## 04｜人生事件交叉验证\nE1、E2、E3。\n## 05｜最终校准结论\n参考时间为09:00。",
            "intervalStart": "08:50", "intervalEnd": "09:10", "referenceTime": "09:00",
            "supportLevel": "中", "limitations": "传统文化分析，不是科学测量。",
            "d1": {"ascendant": {"sign": "白羊"}}, "d9": {"ascendant": {"sign": "天秤"}},
        }
        assert rectification.complete(store, alice["id"], claimed["runId"], result, "test-prompt") is True
        assert rectification.report(store, "alice", alice["id"])["referenceTime"] == "09:00"
        assert rectification.delete_private_data(store, alice["id"]) is True
        completed = rectification.current(store, "alice")["task"]
        assert completed["deletionStatus"] == "deleted" and completed["draft"] == {}
        with store.connect() as db:
            audit = db.execute("SELECT status,result_json FROM rectification_deletions WHERE task_id=?", (alice["id"],)).fetchone()
        assert audit[0] == "completed" and "databaseDraftRows" in audit[1]
        assert rectification.schema_info()["automaticDeletionEnabled"] is True
        times, window = candidate_times("8:30—10:00", "前后30分钟")
        assert times[0] == "08:30" and times[-1] == "10:00" and len(times) <= 25
        assert len(supplemental_questions(data)) <= 3
        raw = json.dumps({"reportMarkdown": result["report"], "result": {"intervalStart": "08:50", "intervalEnd": "09:10", "referenceTime": "09:00", "supportLevel": "中", "limitations": "边界"}}, ensure_ascii=False)
        parsed = parse_model_result(raw, [{"time": "09:00", "d1": result["d1"], "d9": result["d9"]}], window, data)
        assert parsed["referenceTime"] == "09:00"

        def fake_calculate(profile):
            return {"status": "calculated", "ascendant": {"signIndex": 0, "sign": "白羊", "degree": 1.0}, "planets": [{"name": "木星", "signIndex": 1, "sign": "金牛", "degree": 2.0, "house": 2, "retrograde": False}], "dashas": [{"lord": "木星", "start": "2000-01-01T00:00:00+00:00", "end": "2030-01-01T00:00:00+00:00", "subperiods": [{"lord": "土星", "start": "2000-01-01T00:00:00+00:00", "end": "2030-01-01T00:00:00+00:00"}]}]}

        def fake_enrich(chart):
            chart["divisions"] = {"d9": {"ascendant": {"signIndex": 6, "sign": "天秤"}, "planets": [{"name": "木星", "signIndex": 2, "sign": "双子", "house": 9}]}}
            return chart

        def fake_planetary(point):
            return [{"name": name, "signIndex": index, "sign": str(index), "retrograde": False} for index, name in enumerate(("木星", "土星", "Rahu", "Ketu"), 1)]

        facts, calculated, calculated_window = build_analysis(data, {"placeLabel": "上海", "latitude": 31.2, "longitude": 121.4, "timezone": "Asia/Shanghai"}, fake_calculate, fake_enrich, fake_planetary)
        assert calculated and calculated[0]["d1"]["ascendant"]["sign"] == "白羊"
        assert calculated[0]["d9"]["ascendant"]["sign"] == "天秤"
        assert calculated[0]["eventTiming"][0]["period"] == {"mahadasha": "木星", "antardasha": "土星"}
        assert facts["candidateWindow"] == calculated_window

        bob = rectification.start(store, "bob", "paid-b")
        rectification.accept_privacy(store, "bob", bob["id"], True)
        rectification.save_draft(store, "bob", bob["id"], 6, data)
        rectification.submit(store, "bob", bob["id"])
        failed = rectification.claim(store, bob["id"], "contract-reviewed-2026-11-17")
        rectification.fail(store, bob["id"], failed["runId"], "MODEL_FAILED", "test")
        bob_state = rectification.current(store, "bob")["task"]
        assert bob_state["status"] == "failed" and bob_state["draft"]["stage1"]["birthDate"] == "2000-01-01"
    print("rectification smoke test: PASS")


if __name__ == "__main__":
    main()
