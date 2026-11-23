"""Minimal adapter around the existing Jyoti chart engine for rectification."""
import json
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from rectification_prompt import PROMPT_VERSION


TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])(?:[:：]([0-5]\d)|点(半)?)(?!\d)")


def _minute(match):
    return int(match.group(1)) * 60 + (30 if match.group(3) else int(match.group(2) or 0))


def _clock(value):
    value = max(0, min(1439, int(value)))
    return f"{value // 60:02d}:{value % 60:02d}"


def candidate_times(known_time, error_range, maximum=25):
    """Return a bounded, deterministic candidate grid; grid size is not precision."""
    text = (known_time or "").strip()
    found = [_minute(match) for match in TIME_RE.finditer(text)]
    if len(found) >= 2:
        start, end = sorted(found[:2])
    elif found:
        error = (error_range or "").strip()
        amount = re.search(r"(\d{1,3})\s*分", error)
        hours = re.search(r"(\d{1,2}(?:\.5)?)\s*(?:小时|时)", error)
        radius = int(amount.group(1)) if amount else round(float(hours.group(1)) * 60) if hours else 30
        start, end = found[0] - radius, found[0] + radius
    else:
        ranges = (("凌晨", 0, 360), ("上午", 360, 720), ("中午", 660, 840), ("下午", 720, 1080), ("晚上", 1080, 1439))
        match = next(((left, right) for word, left, right in ranges if word in text), None)
        start, end = match or (0, 1439)
    start, end = max(0, start), min(1439, end)
    if start > end:
        raise ValueError("出生时间范围无效")
    span = end - start
    step = max(5, int(math.ceil(max(1, span) / max(1, maximum - 1) / 5) * 5))
    points = list(range(start, end + 1, step))
    if not points or points[-1] != end:
        points.append(end)
    return [_clock(point) for point in points[:maximum]], {"start": _clock(start), "end": _clock(end), "stepMinutes": step, "candidateCount": min(len(points), maximum)}


def supplemental_questions(data):
    """Deterministic preflight questions; never executes chart calculation or AI."""
    questions = []
    first = data.get("stage1", {})
    events = data.get("stage5", {}).get("events", [])
    times, window = candidate_times(first.get("knownTime"), first.get("errorRange"))
    if window["end"] != window["start"] and window["candidateCount"] >= 13:
        questions.append({"id": "time-anchor", "question": "家人是否记得出生发生在饭前、饭后、天亮前后或某个整点节目附近？请写下最客观的时间线索。"})
    complete = [event for event in events if isinstance(event, dict) and event.get("month") and event.get("description")]
    if len(complete) < 5:
        questions.append({"id": "extra-event", "question": "请再补充一个月份明确、影响较大的学业、迁居、入职、关系确立或家庭事件。"})
    categories = {event.get("category") for event in complete}
    if len(categories) < 3:
        questions.append({"id": "different-domain", "question": "现有事件领域较集中，请补充一个不同领域且月份明确的重要转折。"})
    return questions[:3]


def _event_point(month, timezone_name):
    match = re.search(r"((?:19|20|21)\d{2})\D+([01]?\d)", str(month or "").strip())
    if not match:
        raise ValueError("人生事件年月格式无效")
    year, value = map(int, match.groups())
    if not 1 <= value <= 12:
        raise ValueError("人生事件月份必须为1—12月")
    return datetime(year, value, 15, 12, tzinfo=ZoneInfo(timezone_name)).astimezone(timezone.utc)


def _period(chart, point):
    for major in chart.get("dashas", []):
        if datetime.fromisoformat(major["start"]) <= point < datetime.fromisoformat(major["end"]):
            minor = next((item for item in major.get("subperiods", []) if datetime.fromisoformat(item["start"]) <= point < datetime.fromisoformat(item["end"])), None)
            return {"mahadasha": major["lord"], "antardasha": minor["lord"] if minor else None}
    return None


def _chart_summary(chart):
    d9 = chart["divisions"]["d9"]
    return {
        "d1": {
            "ascendant": chart["ascendant"],
            "planets": [{key: planet.get(key) for key in ("name", "sign", "degree", "house", "retrograde")} for planet in chart["planets"]],
        },
        "d9": {"ascendant": d9["ascendant"], "planets": d9["planets"]},
    }


def build_analysis(data, place, calculate, enrich, planetary):
    first = data["stage1"]
    times, window = candidate_times(first.get("knownTime"), first.get("errorRange"))
    events = [event for event in data["stage5"]["events"] if event.get("month") and event.get("description")]
    candidates = []
    for clock in times:
        profile = {
            "date": first["birthDate"], "time": clock, "placeLabel": place["placeLabel"],
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": place["timezone"],
            "accuracy": 0, "fold": None, "consent": True, "coordinateSystem": "WGS84",
        }
        chart = enrich(calculate(profile))
        mapped = []
        for index, event in enumerate(events, 1):
            point = _event_point(event["month"], profile["timezone"])
            transits = []
            for planet in planetary(point):
                if planet["name"] in ("木星", "土星", "Rahu", "Ketu"):
                    transits.append({"name": planet["name"], "sign": planet["sign"], "house": (planet["signIndex"] - chart["ascendant"]["signIndex"]) % 12 + 1, "retrograde": planet.get("retrograde")})
            mapped.append({"eventId": f"E{index}", "month": event["month"], "category": event.get("category"), "impact": event.get("impact"), "period": _period(chart, point), "transits": transits})
        candidates.append({"time": clock, **_chart_summary(chart), "eventTiming": mapped})
    facts = {
        "promptVersion": PROMPT_VERSION,
        "method": {"ayanamsa": "Lahiri", "houses": "Whole Sign", "engine": candidates and "existing Swiss Ephemeris adapter", "candidateGridIsNotPrecision": True},
        "candidateWindow": window,
        "profileEvidence": {key: data.get(key, {}) for key in ("stage2", "stage3", "stage4")},
        "events": [{"eventId": f"E{index}", **event} for index, event in enumerate(events, 1)],
        "supplementalAnswers": data.get("stage6", {}),
        "candidates": candidates,
    }
    return facts, candidates, window


def _model_json(text):
    if isinstance(text, dict):
        return text
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S)
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        start = value.find("{")
        if start >= 0:
            try:
                return json.JSONDecoder().raw_decode(value[start:])[0]
            except (TypeError, ValueError):
                pass
    raise ValueError("校准模型未返回有效 JSON")


def _normalized_clock(value):
    match = re.search(r"(?:[01]?\d|2[0-3])[:：][0-5]\d", str(value or ""))
    if not match:
        return None
    hour, minute = map(int, match.group().replace("：", ":").split(":"))
    return f"{hour:02d}:{minute:02d}"


def parse_model_result(text, candidates, window, private_data):
    result = _model_json(text)
    report = str(result.get("reportMarkdown") or result.get("report") or "").strip()
    final = result.get("result") or {}
    required_titles = ("01｜出生时间校准结论", "02｜D1本命盘验证", "03｜D9九分盘验证", "04｜人生事件交叉验证", "05｜最终校准结论")
    if not report or any(title not in report for title in required_titles):
        raise ValueError("校准报告结构不完整")
    reference = _normalized_clock(final.get("referenceTime"))
    def minutes(clock):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
            raise ValueError("最终时间区间格式无效")
        hour, minute = map(int, clock.split(":"))
        return hour * 60 + minute
    if reference is None:
        raise ValueError("校准模型未返回有效参考时间")
    reference_minutes = minutes(reference)
    candidate = min(candidates, key=lambda item: abs(minutes(item["time"]) - reference_minutes))
    reference = candidate["time"]
    window_left, window_right = minutes(window["start"]), minutes(window["end"])
    left = minutes(_normalized_clock(final.get("intervalStart")) or window["start"])
    right = minutes(_normalized_clock(final.get("intervalEnd")) or window["end"])
    middle = minutes(reference)
    left, right = max(window_left, min(left, middle)), min(window_right, max(right, middle))
    interval_start, interval_end = _clock(left), _clock(right)
    def private_strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from private_strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from private_strings(item)
    for raw in private_strings(private_data):
        if len(raw.strip()) >= 12:
            report = report.replace(raw.strip(), "[已脱敏的原始描述]")
    return {
        "report": report,
        "intervalStart": interval_start,
        "intervalEnd": interval_end,
        "referenceTime": reference,
        "supportLevel": str(final.get("supportLevel") or "有限")[:20],
        "limitations": str(final.get("limitations") or "占星校准属于传统文化分析，并非科学时间测量。")[:1000],
        "d1": candidate["d1"],
        "d9": candidate["d9"],
    }
