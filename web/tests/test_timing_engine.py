from datetime import datetime

from astro import (
    _sun_longitude,
    calculate,
    pratyantardashas,
    sankranti_calendar,
    timing_calendar,
    varshaphala,
)


PROFILE = {
    'date': '1990-06-15',
    'time': '12:30',
    'placeLabel': '上海',
    'latitude': 31.23,
    'longitude': 121.47,
    'timezone': 'Asia/Shanghai',
    'accuracy': 0,
    'consent': True,
    'coordinateSystem': 'WGS84',
}


def angular_error(a, b):
    return abs((a - b + 180) % 360 - 180)


def test_pratyantardasha_is_nine_contiguous_children_of_antardasha():
    chart = calculate(PROFILE)
    minor = chart['dashas'][4]['subperiods'][3]
    periods = pratyantardashas(chart, minor['start'], minor['end'])
    assert len(periods) == 9
    assert periods[0]['pratyantardasha'] == minor['lord']
    assert periods[0]['start'] == minor['start']
    assert periods[-1]['end'] == minor['end']
    assert all(a['end'] == b['start'] for a, b in zip(periods, periods[1:]))


def test_sankranti_calendar_has_twelve_exact_sidereal_ingresses():
    result = sankranti_calendar(2026, 'Asia/Shanghai')
    assert len(result['events']) == 12
    assert {item['signIndex'] for item in result['events']} == set(range(12))
    for item in result['events']:
        assert angular_error(_sun_longitude(datetime.fromisoformat(item['utc'])), item['targetLongitude']) < 1e-5
        assert datetime.fromisoformat(item['local']).year == 2026


def test_varshaphala_solar_return_muntha_and_mudda_cover_one_return_year():
    chart = calculate(PROFILE)
    result = varshaphala(chart, PROFILE, 2026)
    start = datetime.fromisoformat(result['returnUTC'])
    assert angular_error(_sun_longitude(start), result['natalSunLongitude']) < 1e-5
    assert result['ageAtReturn'] == 36
    assert result['muntha']['signIndex'] == (chart['ascendant']['signIndex'] + 36) % 12
    periods = result['muddaDasha']['periods']
    assert periods[0]['start'] == result['returnUTC']
    assert periods[-1]['end'] == result['nextReturnUTC']
    assert all(a['end'] == b['start'] for a, b in zip(periods, periods[1:]))
    assert abs(sum(item['nominalSolarDays'] for item in periods) - 360) < 1e-6


def test_dual_track_windows_are_contiguous_and_have_both_clocks():
    result = timing_calendar(calculate(PROFILE), PROFILE, 2026)
    windows = result['crossWindows']
    assert windows[0]['start'] == result['varshaphala']['returnUTC']
    assert windows[-1]['end'] == result['varshaphala']['nextReturnUTC']
    assert all(a['end'] == b['start'] for a, b in zip(windows, windows[1:]))
    assert all(item['natalTrack'] and item['annualTrack'] for item in windows)
    assert len(result['annualCycleSankrantis']) == 12
