"""
api/routes_stands.py - FMCS 스탠드 제어 API (연속 시뮬레이션 엔진)
================================================================
H형강 압연 공정의 9개 스탠드 실시간 상태, 제어 현황,
운전모드 변경, Load/Speed 차트, 스탠드 상세 데이터를 제공합니다.

매 호출마다 완전 랜덤이 아닌, 시간 기반 연속 시뮬레이션으로
현실적인 데이터를 생성합니다.
"""
import math
import random
import threading
import time
from collections import deque
from datetime import datetime

from fastapi import APIRouter, Depends, Query

import state as st
from api.common import verify_credentials, error_response

router = APIRouter(prefix="/api/stands", tags=["stands"])

# ============================================================
# 공유 상수 및 sin 룩업 테이블
# ============================================================
_TWO_PI = 2.0 * math.pi

# sin 룩업 테이블: 1024 포인트로 0~2π 범위 커버
_SIN_TABLE_SIZE = 1024
_SIN_TABLE = [math.sin(i * _TWO_PI / _SIN_TABLE_SIZE) for i in range(_SIN_TABLE_SIZE)]
_SIN_SCALE = _SIN_TABLE_SIZE / _TWO_PI


def _fast_sin(x: float) -> float:
    """룩업 테이블 기반 sin 근사 (정밀도 ~0.3%, 속도 ~3x)"""
    idx = int(x * _SIN_SCALE) % _SIN_TABLE_SIZE
    return _SIN_TABLE[idx]


# 스탠드 기본값 (3개 시뮬레이터 공유, 불변)
_BASE_RAW = {
    1: {"current": 280, "speed": 2.5, "load": 800,  "temp": 1080},
    2: {"current": 320, "speed": 3.2, "load": 1000, "temp": 1060},
    3: {"current": 380, "speed": 4.0, "load": 1300, "temp": 1040},
    4: {"current": 420, "speed": 4.8, "load": 1500, "temp": 1020},
    5: {"current": 480, "speed": 5.6, "load": 1800, "temp": 1000},
    6: {"current": 530, "speed": 6.5, "load": 2000, "temp": 980},
    7: {"current": 580, "speed": 7.8, "load": 2200, "temp": 960},
    8: {"current": 640, "speed": 9.2, "load": 2500, "temp": 940},
    9: {"current": 720, "speed": 11.0, "load": 2800, "temp": 920},
}

# 모듈 레벨 전용 Random (시뮬레이터 외부에서 사용)
_module_rng = random.Random(99)


# ============================================================
# StandSimulator - 싱글턴 시뮬레이션 엔진
# ============================================================
class StandSimulator:
    """9개 스탠드의 연속적 시뮬레이션 상태"""

    # 스탠드 이름 캐시 (불변)
    _STAND_NAMES = {i: f"S{i}" for i in range(1, 10)}

    def __init__(self, seed_offset=0, current_factor=1.0, speed_factor=1.0, temp_offset=0,
                 ai_auto_init=35, manual_init=4, product_spec="H300x300"):
        self._start = time.time()
        self._lock = threading.Lock()
        self._piece_no = 1
        self._piece_start = time.time()
        self._piece_duration = 45.0  # 1본당 45초
        self._piece_duration_inv = 1.0 / 45.0  # 나눗셈 → 곱셈 변환용
        self._total_pieces = 49
        self._product_spec = product_spec
        # 서버 시작 시 이전 생산분 초기값 (라인별 차별화)
        self._ai_auto_count = ai_auto_init
        self._manual_count = manual_init
        # deque(maxlen) 사용: append O(1), 자동 크기 제한 (pop(0) O(n) 제거)
        self._max_history = 120  # 30초 × 4Hz
        self._history = {i: deque(maxlen=self._max_history) for i in range(1, 10)}

        # 전용 Random 인스턴스 (모듈 전역 random lock 회피)
        self._rng = random.Random(seed_offset)

        # 설비별 차별화 팩터
        self._current_factor = current_factor
        self._speed_factor = speed_factor
        self._temp_offset = temp_offset

        # 공유 _BASE_RAW에서 설비별 팩터 적용한 기본값 계산
        self._base = {}
        for sid, vals in _BASE_RAW.items():
            self._base[sid] = {
                "current": vals["current"] * current_factor,
                "speed": vals["speed"] * speed_factor,
                "load": vals["load"],
                "temp": vals["temp"] + temp_offset,
            }

        # 각 스탠드별 변동 주기(초)와 진폭(%) - 약간씩 다르게
        # 주기 역수(freq)를 미리 계산하여 런타임 나눗셈 제거
        self._wave_params = {}
        rng = random.Random(seed_offset)
        for i in range(1, 10):
            cp = 8 + i * 0.7
            sp = 10 + i * 0.5
            lp = 9 + i * 0.6
            tp = 20 + i
            phase = rng.uniform(0, _TWO_PI)
            self._wave_params[i] = {
                "current_freq": _TWO_PI / cp,
                "current_amp": 0.05 + i * 0.005,
                "speed_freq": _TWO_PI / sp,
                "speed_amp": 0.02,
                "load_freq": _TWO_PI / lp,
                "load_amp": 0.06 + i * 0.004,
                "temp_freq": _TWO_PI / tp,
                "temp_amp": 0.005,
                "phase": phase,
            }

        # 롤갭 기본값 캐시 (stand_id별 불변 부분)
        self._roll_gap_base = {}
        for i in range(1, 10):
            self._roll_gap_base[i] = {
                "ws_base": 12.0 + i * 0.3,
                "ds_base": 11.8 + i * 0.3,
                "h_base": 300.0 + i * 5,
            }

        # piece progress 틱 캐시 (같은 호출 내 중복 계산 방지)
        self._progress_cache_time = 0.0
        self._progress_cache = (0.0, 1)

        # 알람 시뮬레이션
        self._alarm_stand = None
        self._alarm_start = 0
        self._next_alarm = time.time() + self._rng.uniform(180, 300)

    def _get_piece_progress(self):
        """현재 본의 진행률과 스탠드 통과 상황 (틱 내 캐시)"""
        now = time.time()
        # 같은 초(100ms 정밀도) 내 반복 호출 시 캐시 반환
        if now - self._progress_cache_time < 0.1:
            return self._progress_cache

        elapsed = now - self._piece_start
        if elapsed >= self._piece_duration:
            with self._lock:
                # double-check: lock 획득 사이에 다른 스레드가 처리했을 수 있음
                elapsed = time.time() - self._piece_start
                if elapsed >= self._piece_duration:
                    mode = getattr(st, 'OPERATION_MODE', 'ai_auto')
                    if mode == 'ai_auto':
                        if self._rng.random() < 0.90:
                            self._ai_auto_count += 1
                        else:
                            self._manual_count += 1
                    else:
                        self._manual_count += 1
                    self._piece_no = (self._piece_no % self._total_pieces) + 1
                    self._piece_start = time.time()
                    elapsed = 0

        ratio = elapsed * self._piece_duration_inv
        progress = min(100.0, ratio * 100)
        stands_passed = min(9, int(ratio * 9) + 1)
        self._progress_cache_time = now
        self._progress_cache = (progress, stands_passed)
        return progress, stands_passed

    def _get_stand_value(self, stand_id, t, progress_cache=None):
        """시간 t에서의 스탠드 값 계산 - sin 룩업 + 노이즈"""
        base = self._base[stand_id]
        wp = self._wave_params[stand_id]
        phase = wp["phase"]
        rng = self._rng

        # progress 캐시 활용 (get_all_stands에서 전달)
        if progress_cache is not None:
            progress, stands_passed = progress_cache
        else:
            progress, stands_passed = self._get_piece_progress()
        is_loaded = stand_id <= stands_passed

        # 장입 시 부하 증가 효과
        load_factor = 1.3 if is_loaded else 1.0

        # sin 룩업 테이블 + 미세 노이즈 (math.sin → _fast_sin)
        base_current_lf = base["current"] * load_factor
        current = base_current_lf * (
            1 + wp["current_amp"] * _fast_sin(wp["current_freq"] * t + phase)
            + rng.gauss(0, 0.01)
        )
        speed = base["speed"] * (
            1 + wp["speed_amp"] * _fast_sin(wp["speed_freq"] * t + phase + 1)
            + rng.gauss(0, 0.005)
        )
        base_load_lf = base["load"] * load_factor
        load = base_load_lf * (
            1 + wp["load_amp"] * _fast_sin(wp["load_freq"] * t + phase + 2)
            + rng.gauss(0, 0.01)
        )
        temp = base["temp"] * (
            1 + wp["temp_amp"] * _fast_sin(wp["temp_freq"] * t + phase + 3)
            + rng.gauss(0, 0.002)
        )

        # AI 보상값: Manual 모드면 0, AI 모드면 전류 변동 기반 보정
        mode = getattr(st, 'OPERATION_MODE', 'ai_auto')
        if mode == 'ai_auto':
            current_deviation = (current - base_current_lf) / base_current_lf
            ai_comp = round(-current_deviation * 0.5, 3)
        else:
            ai_comp = 0.0

        # 알람 체크
        alarm_ratio = current / base_current_lf
        if self._alarm_stand == stand_id:
            alarm_elapsed = t - (self._alarm_start - self._start)
            status = "alarm" if alarm_elapsed > 30 else "warning"
        elif alarm_ratio > 1.25:
            status = "alarm"
        elif alarm_ratio > 1.15:
            status = "warning"
        else:
            status = "normal"

        # setpoint과 actual (제어값)
        setpoint = round(speed + ai_comp, 3)
        actual = round(speed + rng.gauss(0, 0.02), 3)
        delta = round(setpoint - actual, 4)

        # 롤갭 (캐시된 기본값 사용)
        rg = self._roll_gap_base[stand_id]

        return {
            "id": stand_id,
            "name": self._STAND_NAMES[stand_id],
            "current": round(current, 1),
            "speed": round(speed, 2),
            "ai_comp": ai_comp,
            "load": round(load, 1),
            "status": status,
            "temperature": round(temp, 1),
            "roll_gap": {
                "ws": round(rg["ws_base"] + rng.gauss(0, 0.02), 2),
                "ds": round(rg["ds_base"] + rng.gauss(0, 0.02), 2),
                "h": round(rg["h_base"] + rng.gauss(0, 0.1), 1),
            },
            "setpoint": setpoint,
            "actual": actual,
            "delta": delta,
            "ai_recommendation": round(actual + delta, 3),
            "hmd_loaded": is_loaded,
        }

    def get_all_stands(self):
        """전체 스탠드 상태 조회"""
        t = time.time() - self._start
        self._check_alarm(t)

        # piece progress를 한 번만 계산하여 9개 스탠드에 공유
        progress_cache = self._get_piece_progress()
        stands = [self._get_stand_value(i, t, progress_cache) for i in range(1, 10)]

        # 시계열 버퍼에 추가 (deque maxlen이 자동으로 오래된 항목 제거)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        for s in stands:
            self._history[s["id"]].append({
                "time": ts,
                "current": s["current"],
                "speed": s["speed"],
                "load": s["load"],
                "setpoint": s["setpoint"],
                "actual": s["actual"],
            })

        return stands

    def get_stand_detail(self, stand_id):
        """단일 스탠드 상세 + 시계열"""
        t = time.time() - self._start
        stand = self._get_stand_value(stand_id, t)
        progress, stands_passed = self._get_piece_progress()

        return {
            "stand": stand,
            "control_values": {
                "setpoint": stand["setpoint"],
                "actual": stand["actual"],
                "delta": stand["delta"],
                "ai_recommendation": stand["ai_recommendation"],
                "mode": st.OPERATION_MODE,
            },
            "time_series": list(self._history.get(stand_id, [])),
            "roll_gap": stand["roll_gap"],
            "hmd_loaded": stand["hmd_loaded"],
            "piece_info": {
                "piece_no": self._piece_no,
                "product_spec": self._product_spec,
                "progress": round(progress, 1),
                "stands_passed": stands_passed,
            },
        }

    def _check_alarm(self, t):
        """주기적 알람 이벤트 시뮬레이션"""
        now = time.time()
        if self._alarm_stand and (now - self._alarm_start > 40):
            self._alarm_stand = None
            self._next_alarm = now + self._rng.uniform(180, 300)
        elif not self._alarm_stand and now >= self._next_alarm:
            self._alarm_stand = self._rng.randint(1, 9)
            self._alarm_start = now


# ============================================================
# 설비 목록 및 설비별 시뮬레이터 인스턴스
# ============================================================
EQUIPMENT_LIST = [
    {"id": "FM-LINE1", "name": "사상압연 1라인"},
    {"id": "FM-LINE2", "name": "사상압연 2라인"},
    {"id": "FM-LINE3", "name": "사상압연 3라인"},
]

_simulators = {
    "FM-LINE1": StandSimulator(seed_offset=0, ai_auto_init=35, manual_init=4, product_spec="H300x300"),
    "FM-LINE2": StandSimulator(seed_offset=42, current_factor=1.05, speed_factor=0.97, ai_auto_init=28, manual_init=7, product_spec="H400x400"),
    "FM-LINE3": StandSimulator(seed_offset=77, current_factor=0.97, temp_offset=10, ai_auto_init=42, manual_init=3, product_spec="H250x250"),
}

# 하위호환: 기본 시뮬레이터 참조
_simulator = _simulators["FM-LINE1"]


def _get_simulator(equipment: str) -> StandSimulator:
    """설비 ID로 시뮬레이터 조회 (잘못된 ID → FM-LINE1 폴백)"""
    return _simulators.get(equipment, _simulators["FM-LINE1"])


# ============================================================
# 도메인 상수
# ============================================================
STAND_NAMES = [f"S{i}" for i in range(1, 10)]


_ALARM_TYPES = ("전류 과부하", "온도 이상", "하중 초과", "속도 편차", "롤갭 이상")


def _build_alarms(stands: list, rng: random.Random) -> list:
    """alarm/warning 상태 스탠드에서 알람 목록 생성"""
    alarms = []
    for s in stands:
        if s["status"] == "alarm":
            alarms.append({
                "stand": s["name"],
                "type": rng.choice(_ALARM_TYPES),
                "severity": "high",
                "value": s["current"],
            })
        elif s["status"] == "warning":
            alarms.append({
                "stand": s["name"],
                "type": rng.choice(_ALARM_TYPES),
                "severity": "medium",
                "value": s["current"],
            })
    return alarms


# ============================================================
# GET /api/stands/status - 9개 스탠드 실시간 상태
# ============================================================
@router.get("/equipment-list")
def get_equipment_list(user: dict = Depends(verify_credentials)):
    """사용 가능한 설비 목록 조회"""
    return {"equipment": EQUIPMENT_LIST}


@router.get("/status")
def get_stands_status(
    equipment: str = Query("FM-LINE1"),
    user: dict = Depends(verify_credentials),
):
    """9개 스탠드 실시간 상태 조회 (연속 시뮬레이션)"""
    try:
        sim = _get_simulator(equipment)
        stands = sim.get_all_stands()
        alarms = _build_alarms(stands, sim._rng)
        progress, stands_passed = sim._get_piece_progress()

        # 라인 속도: S9 기준 속도 사용
        line_speed = stands[8]["speed"]

        return {
            "stands": stands,
            "line_speed": round(line_speed, 1),
            "current_production": sim._product_spec,
            "fdt": round(stands[8]["temperature"], 1),
            "ai_confidence": round(0.92 + 0.03 * math.sin(time.time() / 30), 2),
            "shift_oee": round(85 + 5 * math.sin(time.time() / 120), 1),
            "operation_mode": st.OPERATION_MODE,
            "alarms": alarms,
        }
    except Exception as e:
        st.logger.exception("스탠드 상태 조회 실패")
        return error_response(str(e))


# ============================================================
# GET /api/stands/control - 스탠드 제어 현황
# ============================================================
@router.get("/control")
def get_stands_control(
    equipment: str = Query("FM-LINE1"),
    user: dict = Depends(verify_credentials),
):
    """스탠드 제어 현황 조회 (시뮬레이터 데이터 기반)"""
    try:
        sim = _get_simulator(equipment)
        progress, stands_passed = sim._get_piece_progress()
        total_pieces = sim._ai_auto_count + sim._manual_count
        if total_pieces == 0:
            total_pieces = 1  # 0 나눗셈 방지

        # 현재 진행중 + 최근 완료 피스
        pieces = [
            {
                "piece_no": sim._piece_no,
                "product_spec": sim._product_spec,
                "progress": round(progress, 1),
                "status": "in_progress",
                "stands_passed": stands_passed,
            },
            {
                "piece_no": max(1, sim._piece_no - 1),
                "product_spec": sim._product_spec,
                "progress": 100.0,
                "status": "completed",
                "stands_passed": 9,
            },
        ]

        # 롤갭 데이터 (시뮬레이터 기반, 캐시된 기본값 + 전용 rng)
        rng = sim._rng
        roll_gaps = []
        for i in range(1, 10):
            rg = sim._roll_gap_base[i]
            roll_gaps.append({
                "stand": StandSimulator._STAND_NAMES[i],
                "ws": round(rg["ws_base"] + rng.gauss(0, 0.02), 2),
                "ds": round(rg["ds_base"] + rng.gauss(0, 0.02), 2),
                "h": round(rg["h_base"] + rng.gauss(0, 0.1), 1),
            })

        # HMD 상태
        hmd_status = []
        for i in range(1, 10):
            hmd_status.append({"stand": f"S{i}", "loaded": i <= stands_passed})

        return {
            "pieces": pieces,
            "total_pieces": sim._ai_auto_count + sim._manual_count,
            "ai_auto_count": sim._ai_auto_count,
            "manual_count": sim._manual_count,
            "ai_auto_rate": round(sim._ai_auto_count / total_pieces * 100, 2),
            "product_spec": sim._product_spec,
            "roll_gaps": roll_gaps,
            "hmd_status": hmd_status,
            "cascade_mode": True,
        }
    except Exception as e:
        st.logger.exception("스탠드 제어 현황 조회 실패")
        return error_response(str(e))


# ============================================================
# POST /api/stands/operation-mode - 운전모드 변경
# ============================================================
@router.post("/operation-mode")
def change_operation_mode(body: dict, user: dict = Depends(verify_credentials)):
    """운전모드 변경 (ai_auto / manual)"""
    try:
        mode = body.get("mode")
        if mode not in ("ai_auto", "manual"):
            return error_response(f"잘못된 모드: {mode}. 'ai_auto' 또는 'manual'만 가능합니다.")

        st.OPERATION_MODE = mode
        st.logger.info(f"운전모드 변경: {mode}")

        return {
            "status": "success",
            "current_mode": mode,
            "changed_at": datetime.now().isoformat(),
        }
    except Exception as e:
        st.logger.exception("운전모드 변경 실패")
        return error_response(str(e))


# ============================================================
# GET /api/stands/load-speed-chart - Load vs Speed 차트
# ============================================================
@router.get("/load-speed-chart")
def get_load_speed_chart(
    equipment: str = Query("FM-LINE1"),
    user: dict = Depends(verify_credentials),
):
    """Load vs Speed 차트 데이터 (시뮬레이터 시계열 기반)"""
    try:
        sim = _get_simulator(equipment)
        # 시뮬레이터의 시계열 버퍼에서 데이터 추출
        history = sim._history
        max_len = max((len(history[i]) for i in range(1, 10)), default=0)

        if max_len == 0:
            # 아직 데이터가 없으면 현재 상태로 시드
            sim.get_all_stands()
            max_len = 1

        data = []
        for idx in range(max_len):
            point = {}
            for stand_id in range(1, 10):
                buf = history[stand_id]
                if idx < len(buf):
                    entry = buf[idx]
                    point["time"] = entry["time"]
                    name = f"s{stand_id}"
                    point[f"{name}_load"] = entry["load"]
                    point[f"{name}_speed"] = entry["speed"]
            if point:
                data.append(point)

        return {"data": data}
    except Exception as e:
        st.logger.exception("Load/Speed 차트 데이터 생성 실패")
        return error_response(str(e))


# ============================================================
# 생산라인 / 본 / SPC 2단계 검색 API
# ============================================================
@router.get("/production-lines")
def list_production_lines(user: dict = Depends(verify_credentials)):
    """생산라인 목록"""
    return {
        "status": "success",
        "lines": [
            {"id": "FM-LINE1", "name": "사상압연 1라인", "product_spec": "H300x300"},
            {"id": "FM-LINE2", "name": "사상압연 2라인", "product_spec": "H400x400"},
            {"id": "FM-LINE3", "name": "사상압연 3라인", "product_spec": "H250x250"},
        ]
    }


_pieces_cache = {}  # line_id별 캐시 (seed 기반 결정적 → 항상 동일)


@router.get("/production-lines/{line_id}/pieces")
def list_pieces(line_id: str, user: dict = Depends(verify_credentials)):
    """선택한 라인의 생산 본 목록 (시뮬레이션)"""
    if line_id in _pieces_cache:
        return _pieces_cache[line_id]
    rng = random.Random(hash(line_id))
    pieces = []
    spec = "H300x300" if "LINE1" in line_id else ("H400x400" if "LINE2" in line_id else "H250x250")
    for i in range(1, 40):  # 완료된 본만 (1~39)
        pieces.append({
            "piece_no": i,
            "product_spec": spec,
            "status": "completed",
            "start_time": f"2026-03-21 {8 + i // 6:02d}:{(i % 6) * 10:02d}:00",
            "ai_mode": "auto" if rng.random() > 0.49 else "manual",
            "defect_detected": rng.random() < 0.08,
        })
    result = {"status": "success", "line_id": line_id, "pieces": pieces}
    _pieces_cache[line_id] = result
    return result


_spc_cache = {}  # (line_id, piece_no)별 캐시


@router.get("/production-lines/{line_id}/pieces/{piece_no}/spc")
def piece_spc_data(line_id: str, piece_no: int, user: dict = Depends(verify_credentials)):
    """특정 본의 SPC 분석 데이터"""
    cache_key = (line_id, piece_no)
    if cache_key in _spc_cache:
        return _spc_cache[cache_key]
    # 본 번호 기반 seed → 동일 본은 항상 동일 SPC 결과
    rng = random.Random(hash(cache_key))
    spec = "H300x300" if "LINE1" in line_id else ("H400x400" if "LINE2" in line_id else "H250x250")
    target = 300.0 if "LINE1" in line_id else (400.0 if "LINE2" in line_id else 250.0)
    measurements = []
    for i in range(20):  # 20개 서브그룹
        values = [target + rng.gauss(0, 0.15) for _ in range(5)]
        xbar = sum(values) / len(values)
        r = max(values) - min(values)
        measurements.append({"subgroup": i + 1, "xbar": round(xbar, 3), "range": round(r, 3)})

    xbar_mean = sum(m["xbar"] for m in measurements) / len(measurements)
    r_mean = sum(m["range"] for m in measurements) / len(measurements)

    result = {
        "status": "success",
        "line_id": line_id,
        "piece_no": piece_no,
        "product_spec": spec,
        "xbar_chart": {
            "data": measurements,
            "cl": round(xbar_mean, 3),
            "ucl": round(xbar_mean + 0.577 * r_mean, 3),
            "lcl": round(xbar_mean - 0.577 * r_mean, 3),
            "cl_r": round(r_mean, 3),
            "ucl_r": round(2.114 * r_mean, 3),
            "lcl_r": 0,
        },
        "capability": {
            "cp": round(1.3 + rng.gauss(0, 0.1), 2),
            "cpk": round(1.25 + rng.gauss(0, 0.1), 2),
            "pp": round(1.28 + rng.gauss(0, 0.1), 2),
            "ppk": round(1.20 + rng.gauss(0, 0.1), 2),
            "usl": 300.5, "lsl": 299.5, "target": 300.0,
            "mean": round(xbar_mean, 3),
            "std": round(r_mean / 2.326, 4),
        },
        "defect_summary": {
            "thickness_defect": round(rng.uniform(0.5, 2.0), 1),
            "surface_defect": round(rng.uniform(0.3, 1.5), 1),
            "shape_defect": round(rng.uniform(0.2, 1.0), 1),
            "width_defect": round(rng.uniform(0.1, 0.8), 1),
        }
    }
    _spc_cache[cache_key] = result
    return result


# ============================================================
# GET /api/stands/{stand_id}/detail - 단일 스탠드 상세
# ============================================================
@router.get("/{stand_id}/detail")
def get_stand_detail(
    stand_id: int,
    equipment: str = Query("FM-LINE1"),
    user: dict = Depends(verify_credentials),
):
    """단일 스탠드 상세 정보 + 시계열 데이터"""
    try:
        if stand_id < 1 or stand_id > 9:
            return error_response(f"잘못된 스탠드 ID: {stand_id}. 1~9 범위만 가능합니다.")
        sim = _get_simulator(equipment)
        return sim.get_stand_detail(stand_id)
    except Exception as e:
        st.logger.exception(f"스탠드 {stand_id} 상세 조회 실패")
        return error_response(str(e))
