"""
ml/process_optimizer.py - 공정 파라미터 최적화 (ML + P-PSO)
===========================================================
제조 AI 솔루션

설비별 공정 파라미터를 최적화하여 수율 최대화 + 불량률 최소화

핵심 기능:
1. 파라미터별 효율 계산: 각 공정 파라미터의 수율 기여도 및 불량 영향
2. P-PSO 최적화: 설비별 파라미터 범위 제약 하에서 최적 공정 조건 탐색
3. 설비별 맞춤: 설비 유형/상태에 따라 다른 최적화 결과
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging
import json

logger = logging.getLogger(__name__)

# 프로젝트 루트
try:
    PROJECT_ROOT = Path(__file__).parent.parent
except NameError:
    # 주피터 노트북 실행 시
    if 'BACKEND_DIR' in dir():
        PROJECT_ROOT = BACKEND_DIR
    else:
        _cwd = Path(".").resolve()
        if _cwd.name == "ml":
            PROJECT_ROOT = _cwd.parent
        else:
            PROJECT_ROOT = _cwd

# CSV 데이터 캐시 (매 호출 시 중복 I/O 방지)
_CSV_CACHE: Dict[str, pd.DataFrame] = {}


_CSV_CACHE_MAX_SIZE = 10  # 메모리 최적화: 캐시 최대 항목 수


def _load_csv_cached(path: Path) -> Optional[pd.DataFrame]:
    """CSV 로드 결과를 캐싱 (매 호출 시 중복 I/O 방지)"""
    key = str(path)
    if key in _CSV_CACHE:
        return _CSV_CACHE[key]
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        # 메모리 최적화: 캐시가 maxsize 초과 시 가장 오래된 항목 제거
        if len(_CSV_CACHE) >= _CSV_CACHE_MAX_SIZE:
            oldest_key = next(iter(_CSV_CACHE))
            del _CSV_CACHE[oldest_key]
            logger.debug(f"CSV cache evicted oldest: {oldest_key}")
        _CSV_CACHE[key] = df
        return df
    except Exception as e:
        logger.warning(f"CSV load failed: {path} - {e}")
        return None

# ========================================
# 공정 파라미터 정의 및 기본값
# ========================================

# 최적화 대상 공정 파라미터
PROCESS_PARAMETERS = [
    'temperature',    # 공정 온도 (도)
    'pressure',       # 공정 압력 (bar)
    'speed',          # 가공 속도 (rpm 또는 m/min)
    'feed_rate',      # 이송률 (mm/min)
]

# 설비 유형별 파라미터 범위 및 기본값
DEFAULT_PARAM_RANGES = {
    'CNC': {
        'temperature': {
            'name': '공정 온도',
            'min': 15, 'max': 80,
            'optimal_range': (30, 55),
            'unit': '°C',
            'yield_impact': 0.15,       # 수율 기여도
            'defect_sensitivity': 0.20,  # 불량률 민감도
        },
        'pressure': {
            'name': '절삭 압력',
            'min': 2.0, 'max': 12.0,
            'optimal_range': (4.0, 8.0),
            'unit': 'bar',
            'yield_impact': 0.10,
            'defect_sensitivity': 0.15,
        },
        'speed': {
            'name': '스핀들 회전수',
            'min': 500, 'max': 15000,
            'optimal_range': (3000, 8000),
            'unit': 'rpm',
            'yield_impact': 0.25,
            'defect_sensitivity': 0.25,
        },
        'feed_rate': {
            'name': '이송률',
            'min': 50, 'max': 2000,
            'optimal_range': (200, 800),
            'unit': 'mm/min',
            'yield_impact': 0.20,
            'defect_sensitivity': 0.15,
        },
    },
    '프레스': {
        'temperature': {
            'name': '금형 온도',
            'min': 20, 'max': 200,
            'optimal_range': (60, 120),
            'unit': '°C',
            'yield_impact': 0.20,
            'defect_sensitivity': 0.25,
        },
        'pressure': {
            'name': '성형 압력',
            'min': 50, 'max': 500,
            'optimal_range': (150, 350),
            'unit': 'ton',
            'yield_impact': 0.30,
            'defect_sensitivity': 0.30,
        },
        'speed': {
            'name': '프레스 속도',
            'min': 5, 'max': 100,
            'optimal_range': (20, 60),
            'unit': 'spm',
            'yield_impact': 0.15,
            'defect_sensitivity': 0.20,
        },
        'feed_rate': {
            'name': '자재 이송',
            'min': 10, 'max': 200,
            'optimal_range': (30, 100),
            'unit': 'mm/stroke',
            'yield_impact': 0.10,
            'defect_sensitivity': 0.10,
        },
    },
    '사출': {
        'temperature': {
            'name': '사출 온도',
            'min': 150, 'max': 350,
            'optimal_range': (200, 280),
            'unit': '°C',
            'yield_impact': 0.30,
            'defect_sensitivity': 0.35,
        },
        'pressure': {
            'name': '사출 압력',
            'min': 30, 'max': 200,
            'optimal_range': (80, 150),
            'unit': 'MPa',
            'yield_impact': 0.25,
            'defect_sensitivity': 0.25,
        },
        'speed': {
            'name': '사출 속도',
            'min': 10, 'max': 300,
            'optimal_range': (50, 200),
            'unit': 'mm/s',
            'yield_impact': 0.20,
            'defect_sensitivity': 0.20,
        },
        'feed_rate': {
            'name': '보압',
            'min': 20, 'max': 150,
            'optimal_range': (50, 100),
            'unit': 'MPa',
            'yield_impact': 0.15,
            'defect_sensitivity': 0.15,
        },
    },
}

# 기타 설비 유형은 범용 범위 사용
DEFAULT_GENERIC_PARAMS = {
    'temperature': {
        'name': '공정 온도',
        'min': 15, 'max': 100,
        'optimal_range': (30, 65),
        'unit': '°C',
        'yield_impact': 0.15,
        'defect_sensitivity': 0.20,
    },
    'pressure': {
        'name': '공정 압력',
        'min': 1.0, 'max': 15.0,
        'optimal_range': (3.0, 10.0),
        'unit': 'bar',
        'yield_impact': 0.15,
        'defect_sensitivity': 0.15,
    },
    'speed': {
        'name': '가공 속도',
        'min': 100, 'max': 5000,
        'optimal_range': (500, 3000),
        'unit': 'rpm',
        'yield_impact': 0.20,
        'defect_sensitivity': 0.20,
    },
    'feed_rate': {
        'name': '이송률',
        'min': 10, 'max': 500,
        'optimal_range': (50, 300),
        'unit': 'mm/min',
        'yield_impact': 0.15,
        'defect_sensitivity': 0.15,
    },
}


class ProcessOptimizer:
    """공정 파라미터 최적화기"""

    def __init__(self, equipment_id: str, equipment_type: str = None, goal: str = 'balanced'):
        """
        Args:
            equipment_id: 설비 ID
            equipment_type: 설비 유형 (CNC, 프레스, 사출 등). None이면 데이터에서 로드.
            goal: 'maximize_yield' | 'minimize_defect' | 'balanced'
        """
        self.equipment_id = equipment_id
        self.equipment_type = equipment_type
        self.goal = goal

        self.equipment_data = None
        self.equipment_analytics = None
        self.param_ranges = None
        self.yield_predictor = None

        self._load_data()
        self._load_yield_model()
        self._initialize_param_ranges()

    def _load_data(self):
        """설비 데이터 로딩 (캐시 활용으로 중복 I/O 제거)"""
        try:
            # 설비 기본 데이터
            all_equipment = _load_csv_cached(PROJECT_ROOT / "equipment.csv")
            if all_equipment is not None:
                eq_row = all_equipment[all_equipment['equipment_id'] == self.equipment_id]
                if len(eq_row) > 0:
                    self.equipment_data = eq_row.iloc[0].to_dict()
                    if self.equipment_type is None:
                        self.equipment_type = self.equipment_data.get('equipment_type', 'CNC')
                    logger.info(f"Loaded equipment data for {self.equipment_id}")
                else:
                    logger.warning(f"Equipment {self.equipment_id} not found in equipment.csv")
                    self.equipment_data = {}
            else:
                logger.warning("equipment.csv not found")
                self.equipment_data = {}

            # 설비 분석 데이터
            all_analytics = _load_csv_cached(PROJECT_ROOT / "equipment_analytics.csv")
            if all_analytics is not None:
                analytics_row = all_analytics[all_analytics['equipment_id'] == self.equipment_id]
                if len(analytics_row) > 0:
                    self.equipment_analytics = analytics_row.iloc[0].to_dict()
                    logger.info(f"Loaded analytics for {self.equipment_id}")
                else:
                    logger.warning(f"Equipment {self.equipment_id} not found in equipment_analytics.csv")
                    self.equipment_analytics = {}
            else:
                logger.warning("equipment_analytics.csv not found")
                self.equipment_analytics = {}

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    def _load_yield_model(self):
        """수율 예측 모델 로딩"""
        try:
            from ml.yield_model import get_predictor
            self.yield_predictor = get_predictor()
            if self.yield_predictor and self.yield_predictor.is_fitted:
                logger.info("Yield predictor loaded successfully")
            else:
                logger.warning("Yield predictor not fitted")
                self.yield_predictor = None
        except Exception as e:
            logger.warning(f"Failed to load yield model: {e}")
            self.yield_predictor = None

    def _initialize_param_ranges(self):
        """
        설비 유형 기반으로 파라미터 범위 초기화

        설비 유형에 맞는 파라미터 범위를 설정하고,
        설비 분석 데이터가 있으면 현재 상태를 반영
        """
        # 설비 유형별 범위 가져오기
        type_params = DEFAULT_PARAM_RANGES.get(self.equipment_type, None)

        self.param_ranges = {}
        for param in PROCESS_PARAMETERS:
            if type_params and param in type_params:
                params = type_params[param].copy()
            else:
                params = DEFAULT_GENERIC_PARAMS[param].copy()

            # 설비 분석 데이터에서 현재값 반영
            if self.equipment_analytics:
                current_key = param
                if current_key in self.equipment_analytics and not pd.isna(self.equipment_analytics.get(current_key)):
                    params['current_value'] = float(self.equipment_analytics[current_key])

            self.param_ranges[param] = params

    def calculate_param_efficiency(
        self,
        param: str,
        value: float
    ) -> Dict[str, Any]:
        """
        특정 파라미터 값에 대한 효율 계산

        최적 범위(optimal_range) 기반 효율 모델:
        - 최적 범위 내: 최대 효율
        - 범위 벗어남: 거리에 비례하여 효율 감소

        Args:
            param: 파라미터 이름 (temperature, pressure, speed, feed_rate)
            value: 파라미터 값

        Returns:
            {
                'parameter': str,
                'value': float,
                'yield_contribution': float,     # 수율 기여도 (0~1)
                'defect_risk': float,             # 불량 위험도 (0~1)
                'efficiency_score': float,        # 종합 효율 점수
                'in_optimal_range': bool,
            }
        """
        params = self.param_ranges.get(param)
        if params is None:
            return {'error': f'Unknown parameter: {param}'}

        opt_min, opt_max = params['optimal_range']
        param_min, param_max = params['min'], params['max']

        if value < param_min or value > param_max:
            return {
                'parameter': param,
                'parameter_name': params['name'],
                'value': round(value, 2),
                'unit': params['unit'],
                'yield_contribution': 0.0,
                'defect_risk': 1.0,
                'efficiency_score': 0.0,
                'in_optimal_range': False,
                'warning': '파라미터가 허용 범위를 벗어났습니다',
            }

        # 최적 범위 내 여부
        in_optimal = opt_min <= value <= opt_max

        if in_optimal:
            # 최적 범위 내: 높은 수율, 낮은 불량
            yield_contrib = params['yield_impact']
            defect_risk = 0.02  # 최소 불량 위험
        else:
            # 범위 벗어남: 거리에 비례한 효율 감소
            if value < opt_min:
                distance = (opt_min - value) / (opt_min - param_min + 1e-8)
            else:
                distance = (value - opt_max) / (param_max - opt_max + 1e-8)

            yield_contrib = params['yield_impact'] * (1.0 - distance * 0.8)
            defect_risk = params['defect_sensitivity'] * distance

        # 종합 효율 점수
        efficiency_score = yield_contrib * (1 - defect_risk) * 100

        return {
            'parameter': param,
            'parameter_name': params['name'],
            'value': round(value, 2),
            'unit': params['unit'],
            'yield_contribution': round(yield_contrib, 4),
            'defect_risk': round(defect_risk, 4),
            'efficiency_score': round(efficiency_score, 4),
            'in_optimal_range': in_optimal,
        }

    def optimize(
        self,
        max_iterations: int = 200,
        population_size: int = 50,
    ) -> Dict[str, Any]:
        """
        P-PSO로 최적 공정 파라미터 탐색

        Args:
            max_iterations: P-PSO 반복 횟수 (기본 200)
            population_size: P-PSO 개체 수 (기본 50)

        Returns:
            {
                'equipment_id': str,
                'equipment_type': str,
                'goal': str,
                'optimal_parameters': [...],    # 최적 파라미터 목록
                'expected_yield_rate': float,
                'expected_defect_rate': float,
                'optimization_method': str,
            }
        """
        # P-PSO 최적화 시도
        try:
            optimal_params = self._run_pso_optimization(max_iterations, population_size)
        except Exception as e:
            logger.warning(f"PSO optimization failed: {e}, using heuristic fallback")
            optimal_params = self._heuristic_optimization()

        # 결과 조합
        results = []
        for param, value in optimal_params.items():
            param_result = self.calculate_param_efficiency(param, value)
            results.append(param_result)

        # 수율 예측 모델이 있으면 예측 수율도 포함
        predicted_yield = None
        if self.yield_predictor and self.equipment_analytics:
            try:
                features = {
                    'equipment_type': self.equipment_analytics.get('equipment_type_encoded', 0),
                    'operating_hours': self.equipment_analytics.get('operating_hours', 0),
                    'vibration': self.equipment_analytics.get('vibration', 0),
                    'temperature': optimal_params.get('temperature', 50),
                    'pressure': optimal_params.get('pressure', 5),
                    'material_quality': 8,
                    'operator_experience': 5,
                }
                predicted_yield = self.yield_predictor.predict(features)
            except Exception as e:
                logger.warning(f"Yield prediction failed: {e}")

        # 예상 수율 및 불량률 계산
        total_yield_contrib = sum(r.get('yield_contribution', 0) for r in results)
        total_defect_risk = sum(r.get('defect_risk', 0) for r in results)
        n_params = len(results) if results else 1
        avg_defect_risk = total_defect_risk / n_params

        expected_yield = min(100, 90 + total_yield_contrib * 15)  # 기본 90% + 기여도 보너스
        expected_defect = max(0.01, avg_defect_risk * 5)  # 불량률 (%)

        # 현재값과 비교
        current_comparison = []
        for param in PROCESS_PARAMETERS:
            current_val = self.param_ranges[param].get('current_value')
            optimal_val = optimal_params.get(param)
            if current_val is not None and optimal_val is not None:
                current_comparison.append({
                    'parameter': param,
                    'parameter_name': self.param_ranges[param]['name'],
                    'current_value': round(current_val, 2),
                    'optimal_value': round(optimal_val, 2),
                    'change': round(optimal_val - current_val, 2),
                    'unit': self.param_ranges[param]['unit'],
                })

        output = {
            'equipment_id': self.equipment_id,
            'equipment_type': self.equipment_type,
            'goal': self.goal,
            'optimal_parameters': sorted(results, key=lambda x: x.get('efficiency_score', 0), reverse=True),
            'expected_yield_rate': round(expected_yield, 1),
            'expected_defect_rate': round(expected_defect, 2),
            'current_vs_optimal': current_comparison,
            'optimization_method': 'P-PSO (Phasor Particle Swarm Optimization)',
        }

        if predicted_yield is not None:
            output['ml_predicted_yield'] = round(predicted_yield, 1)

        return output

    def _heuristic_optimization(self) -> Dict[str, float]:
        """
        P-PSO 실패 시 휴리스틱 최적화 (fallback)

        전략: 각 파라미터의 최적 범위 중앙값 사용
        """
        optimal = {}
        for param in PROCESS_PARAMETERS:
            params = self.param_ranges[param]
            opt_min, opt_max = params['optimal_range']
            # 최적 범위 중앙값 + 약간의 랜덤 오프셋
            center = (opt_min + opt_max) / 2
            offset = (opt_max - opt_min) * np.random.uniform(-0.1, 0.1)
            optimal[param] = round(center + offset, 2)

        return optimal

    def _run_pso_optimization(
        self,
        max_iterations: int,
        population_size: int,
    ) -> Dict[str, float]:
        """
        P-PSO 최적화 실행 - 연속 변수로 파라미터값 탐색

        각 차원: 파라미터 값 (min ~ max 범위)
        목적: 수율 최대화 + 불량률 최소화
        """
        from mealpy.swarm_based.PSO import P_PSO
        from mealpy.utils.space import FloatVar
        logger.info(f"Using P_PSO with {max_iterations} iterations, pop_size={population_size}")

        n_params = len(PROCESS_PARAMETERS)

        if n_params == 0:
            raise ValueError("최적화할 파라미터가 없습니다")

        # 파라미터 범위 설정
        lower_bounds = []
        upper_bounds = []
        for param in PROCESS_PARAMETERS:
            params = self.param_ranges[param]
            lower_bounds.append(float(params['min']))
            upper_bounds.append(float(params['max']))

        # 파라미터 사전 추출 (vectorized fitness용)
        _opt_mins = np.array([self.param_ranges[p]['optimal_range'][0] for p in PROCESS_PARAMETERS])
        _opt_maxs = np.array([self.param_ranges[p]['optimal_range'][1] for p in PROCESS_PARAMETERS])
        _param_mins = np.array([self.param_ranges[p]['min'] for p in PROCESS_PARAMETERS])
        _param_maxs = np.array([self.param_ranges[p]['max'] for p in PROCESS_PARAMETERS])
        _yield_impacts = np.array([self.param_ranges[p]['yield_impact'] for p in PROCESS_PARAMETERS])
        _defect_sens = np.array([self.param_ranges[p]['defect_sensitivity'] for p in PROCESS_PARAMETERS])

        def fitness_function(solution):
            """numpy vectorized fitness function"""
            values = np.array(solution)

            # 최적 범위 내 여부 판단
            in_range = (values >= _opt_mins) & (values <= _opt_maxs)

            # 거리 계산 (범위 벗어난 정도)
            below_dist = np.where(values < _opt_mins,
                                  (_opt_mins - values) / (_opt_mins - _param_mins + 1e-8), 0)
            above_dist = np.where(values > _opt_maxs,
                                  (values - _opt_maxs) / (_param_maxs - _opt_maxs + 1e-8), 0)
            distance = below_dist + above_dist

            # 수율 기여도 계산
            yield_contrib = np.where(in_range,
                                     _yield_impacts,
                                     _yield_impacts * (1.0 - distance * 0.8))

            # 불량 위험도 계산
            defect_risk = np.where(in_range,
                                   0.02,
                                   _defect_sens * distance)

            total_yield = np.sum(yield_contrib)
            total_defect = np.mean(defect_risk)

            if self.goal == 'maximize_yield':
                total_score = total_yield * 100 - total_defect * 20
            elif self.goal == 'minimize_defect':
                total_score = -total_defect * 100 + total_yield * 20
            else:  # balanced
                total_score = total_yield * 60 - total_defect * 40

            # 범위 내 파라미터 수 보너스
            in_range_bonus = np.sum(in_range) * 5
            total_score += in_range_bonus

            return float(total_score)

        # mealpy 3.x 방식: FloatVar 사용
        bounds = FloatVar(lb=lower_bounds, ub=upper_bounds, name="process_params")

        problem = {
            "obj_func": fitness_function,
            "bounds": bounds,
            "minmax": "max",
        }

        # P_PSO 실행
        model = P_PSO(epoch=max_iterations, pop_size=population_size)
        best_agent = model.solve(problem)
        best_solution = np.array(best_agent.solution)

        # 결과 변환
        optimal_params = {}
        for i, param in enumerate(PROCESS_PARAMETERS):
            optimal_params[param] = round(float(best_solution[i]), 2)

        # 로그 출력
        results = [self.calculate_param_efficiency(p, v) for p, v in optimal_params.items()]
        in_range_count = sum(1 for r in results if r.get('in_optimal_range', False))
        logger.info(
            f"P_PSO 최적화 완료: {in_range_count}/{len(PROCESS_PARAMETERS)}개 파라미터 최적범위 내"
        )

        return optimal_params
