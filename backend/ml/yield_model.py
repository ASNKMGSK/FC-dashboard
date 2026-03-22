"""
ml/yield_model.py - 수율 예측 모델
===================================
제조 AI 솔루션

설비 공정 파라미터 기반 수율(yield_rate) 예측 모델 학습 및 추론

입력: equipment_type, operating_hours, vibration, temperature, pressure,
      material_quality, operator_experience
출력: predicted_yield_rate (예측 수율, %)

[주피터 노트북에서 실행 시]
이 파일 전체를 복사해서 셀에 붙여넣고 실행하면 됩니다.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import joblib
import logging
from typing import Dict, List, Optional, Tuple
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)

# ========================================
# MLflow 설정 (train_models.py와 동일)
# ========================================
try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    print("MLflow not available - skipping experiment tracking")

# 프로젝트 루트 (주피터/스크립트 호환)
try:
    # 스크립트 실행 시
    PROJECT_ROOT = Path(__file__).parent.parent
except NameError:
    # 주피터 노트북 실행 시
    # 이미 BACKEND_DIR이 정의되어 있으면 사용
    if 'BACKEND_DIR' in dir():
        PROJECT_ROOT = BACKEND_DIR
    else:
        # ml 폴더에서 실행 시 부모 폴더로
        _cwd = Path(".").resolve()
        if _cwd.name == "ml":
            PROJECT_ROOT = _cwd.parent
        else:
            PROJECT_ROOT = _cwd

# 수율 예측 피처 컬럼
YIELD_FEATURES = [
    'equipment_type',         # 설비 유형 (인코딩)
    'operating_hours',        # 가동시간
    'vibration',              # 진동값
    'temperature',            # 온도
    'pressure',               # 압력
    'material_quality',       # 자재 품질 (1~10)
    'operator_experience',    # 작업자 경력 (년)
]

# 모델 저장 경로
MODEL_PATH = PROJECT_ROOT / "model_yield.pkl"
SCALER_PATH = PROJECT_ROOT / "scaler_yield.pkl"


class YieldPredictor:
    """설비 공정 파라미터 기반 수율 예측 모델"""

    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_fitted = False

    def _generate_synthetic_data(
        self,
        base_df: pd.DataFrame,
        n_samples: int = 500
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        기존 데이터 기반 합성 데이터 생성

        전략:
        - 기존 공정 데이터에 노이즈를 추가해서 augmentation
        - 공정 파라미터 변화에 따른 수율 변화 시뮬레이션
        """
        logger.info(f"Generating {n_samples} synthetic samples from {len(base_df)} base records")

        # 피처별 수율 영향도 (제조 도메인 기반 추정)
        # equipment_type, operating_hours, vibration, temperature, pressure, material_quality, operator_experience
        impact_values = np.array([0.5, -0.001, -0.5, -0.3, -0.2, 1.0, 0.3])

        samples_per_record = max(1, n_samples // len(base_df))
        n_records = len(base_df)
        n_features = len(YIELD_FEATURES)

        # 원본 데이터를 행렬로 추출
        base_X = base_df[YIELD_FEATURES].values  # (n_records, n_features)
        base_y = base_df.get('next_yield_rate',
                            base_df.get('yield_rate', pd.Series([95.0] * len(base_df)))).values

        # Broadcasting으로 합성 데이터 일괄 생성
        total_synthetic = n_records * samples_per_record
        noise_pct = np.random.uniform(-0.15, 0.15, (total_synthetic, n_features))

        # 각 레코드별 반복 인덱스
        record_indices = np.repeat(np.arange(n_records), samples_per_record)
        base_features_repeated = base_X[record_indices]  # (total_synthetic, n_features)
        base_y_repeated = base_y[record_indices]  # (total_synthetic,)

        # 변화량 계산
        changes = base_features_repeated * noise_pct  # (total_synthetic, n_features)
        new_features = np.maximum(0, base_features_repeated + changes)

        # 수율 변화 = 변화량 * 영향도의 내적
        delta_yield = np.sum(changes * impact_values, axis=1)

        # 노이즈 추가
        noise_std = 1.0  # 수율 ±1% 노이즈
        noise = np.random.normal(0, noise_std, total_synthetic)
        new_y = np.clip(base_y_repeated + delta_yield + noise, 70, 100)

        # 원본 데이터 합치기
        X_all = np.vstack([new_features, base_X])
        y_all = np.concatenate([new_y, base_y])

        return X_all, y_all

    def train(self, equipment_data_df: pd.DataFrame, n_synthetic: int = 500) -> Dict:
        """
        모델 학습

        Args:
            equipment_data_df: 설비 공정 데이터프레임
                필수 컬럼: equipment_type, operating_hours, vibration,
                          temperature, pressure, material_quality, operator_experience
                선택 컬럼: next_yield_rate (없으면 yield_rate * 1.001 로 추정)
            n_synthetic: 생성할 합성 데이터 수

        Returns:
            학습 결과 (cv_score, feature_importance 등)
        """
        logger.info("Training yield prediction model...")

        # 합성 데이터 생성
        X, y = self._generate_synthetic_data(equipment_data_df, n_synthetic)

        # 스케일링
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # 모델 학습 (LightGBM)
        self.model = lgb.LGBMRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            num_leaves=15,
            min_child_samples=3,
            random_state=42,
            verbose=-1
        )

        # 교차 검증
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring='r2')

        # 전체 데이터로 최종 학습
        self.model.fit(X_scaled, y)
        self.is_fitted = True

        # feature importance
        feature_importance = dict(zip(YIELD_FEATURES, self.model.feature_importances_))

        result = {
            'cv_r2_mean': float(np.mean(cv_scores)),
            'cv_r2_std': float(np.std(cv_scores)),
            'n_samples': len(X),
            'feature_importance': feature_importance,
        }

        logger.info(f"Model trained: R2 = {result['cv_r2_mean']:.3f} (+/- {result['cv_r2_std']:.3f})")

        return result

    def predict(self, features: Dict[str, float]) -> float:
        """
        수율 예측

        Args:
            features: {
                'equipment_type': 0,         # 설비 유형 인코딩값
                'operating_hours': 15000,    # 가동시간
                'vibration': 2.5,            # 진동값
                'temperature': 45,           # 온도
                'pressure': 5.0,             # 압력
                'material_quality': 8,       # 자재 품질 (1~10)
                'operator_experience': 5,    # 작업자 경력 (년)
            }

        Returns:
            예측 수율 (%, 70~100 범위)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call train() or load() first.")

        X = np.array([[features.get(feat, 0) for feat in YIELD_FEATURES]])
        X_scaled = self.scaler.transform(X)
        pred = self.model.predict(X_scaled)[0]

        return float(np.clip(pred, 70, 100))  # 70~100% 범위 제한

    def save(self, model_path: Path = MODEL_PATH, scaler_path: Path = SCALER_PATH):
        """모델 저장"""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted.")

        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Model saved to {model_path}")

    def load(self, model_path: Path = MODEL_PATH, scaler_path: Path = SCALER_PATH) -> bool:
        """모델 로딩"""
        try:
            if model_path.exists() and scaler_path.exists():
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                self.is_fitted = True
                logger.info(f"Model loaded from {model_path}")
                return True
            else:
                logger.warning(f"Model file not found: {model_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False


# 전역 인스턴스 (싱글톤 패턴)
_predictor_instance: Optional[YieldPredictor] = None


def get_predictor() -> YieldPredictor:
    """수율 예측 모델 인스턴스 반환"""
    global _predictor_instance

    if _predictor_instance is None:
        _predictor_instance = YieldPredictor()
        # 저장된 모델 로딩 시도
        _predictor_instance.load()

    return _predictor_instance


def train_and_save(equipment_data_df: pd.DataFrame, register_mlflow: bool = True) -> Dict:
    """
    모델 학습 및 저장 (MLflow 등록 포함)

    Args:
        equipment_data_df: 설비 공정 데이터프레임
        register_mlflow: MLflow에 등록 여부 (기본 True)

    Returns:
        학습 결과 dict
    """
    predictor = YieldPredictor()
    result = predictor.train(equipment_data_df)
    predictor.save()

    # 전역 인스턴스 업데이트
    global _predictor_instance
    _predictor_instance = predictor

    # MLflow 등록
    if register_mlflow and MLFLOW_AVAILABLE:
        try:
            # MLflow 설정 (train_models.py와 동일한 경로)
            mlflow_tracking_uri = f"file:{PROJECT_ROOT / 'ml' / 'mlruns'}"
            mlflow.set_tracking_uri(mlflow_tracking_uri)

            experiment_name = "smart-factory-ai"
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                mlflow.create_experiment(experiment_name)
            mlflow.set_experiment(experiment_name)

            with mlflow.start_run(run_name="yield_model"):
                # 태그
                mlflow.set_tag("model_type", "regression")
                mlflow.set_tag("target", "yield_rate")
                mlflow.set_tag("algorithm", "LightGBM")
                mlflow.set_tag("domain", "manufacturing")

                # 하이퍼파라미터
                mlflow.log_params({
                    "n_estimators": 100,
                    "max_depth": 4,
                    "learning_rate": 0.1,
                    "num_leaves": 15,
                    "min_child_samples": 3,
                    "n_features": len(YIELD_FEATURES),
                    "n_samples": result['n_samples'],
                })

                # 메트릭
                mlflow.log_metrics({
                    "cv_r2_mean": result['cv_r2_mean'],
                    "cv_r2_std": result['cv_r2_std'],
                })

                # 모델 등록
                mlflow.sklearn.log_model(
                    predictor.model,
                    "yield_model",
                    registered_model_name="수율예측"
                )

                print(f"[MLflow] Run ID: {mlflow.active_run().info.run_id}")
                print(f"[MLflow] Model registered as '수율예측'")

        except Exception as e:
            logger.warning(f"MLflow registration failed: {e}")
            print(f"[Warning] MLflow 등록 실패: {e}")

    return result
