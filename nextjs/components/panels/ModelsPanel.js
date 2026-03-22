// components/panels/ModelsPanel.js
// 스마트팩토리 AI 플랫폼 - MLOps 대시보드 패널 (FMCS 업그레이드)

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Layers, FlaskConical, RefreshCw, CheckCircle, XCircle,
  Activity, AlertTriangle, TrendingUp, BarChart3, Shield,
  Sliders, GitBranch, Play, RotateCcw, Download,
  Beaker, Scale, Clock, Award
} from 'lucide-react';
import SectionHeader from '@/components/SectionHeader';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, Cell
} from 'recharts';

// 상태 배지 컴포넌트
const StatusBadge = ({ status, size = 'sm' }) => {
  const config = {
    '정상': { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300' },
    '주의': { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300' },
    '위험': { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300' },
    'OK': { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300' },
    'WARNING': { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300' },
    'CRITICAL': { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300' },
  }[status] || { bg: 'bg-gray-100', text: 'text-gray-600', border: 'border-gray-300' };

  const sizeClass = size === 'lg'
    ? 'text-xs px-3 py-1'
    : 'text-[10px] px-2 py-0.5';

  return (
    <span className={`${sizeClass} rounded-full font-bold border ${config.bg} ${config.text} ${config.border}`}>
      {status}
    </span>
  );
};

// 차트 커스텀 툴팁
const ChartTooltip = ({ active, payload, label, unit = '' }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border-2 border-sf-orange/20 bg-white/95 px-3 py-2 shadow-lg backdrop-blur text-xs">
      <p className="font-bold text-sf-brown mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-semibold">
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}{unit}
        </p>
      ))}
    </div>
  );
};

// PSI 바 색상
const PSI_COLORS = { OK: '#22c55e', WARNING: '#eab308', CRITICAL: '#ef4444' };

// 카드 애니메이션 변형
const cardVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } },
};

// 숫자 애니메이션 컴포넌트
const AnimatedNumber = ({ value, decimals = 4 }) => {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    if (value === null || value === undefined) return;
    const start = display || 0;
    const diff = value - start;
    const steps = 20;
    let step = 0;
    const timer = setInterval(() => {
      step++;
      setDisplay(start + diff * (step / steps));
      if (step >= steps) clearInterval(timer);
    }, 20);
    return () => clearInterval(timer);
  }, [value]);
  if (value === null || value === undefined) return '-';
  return display.toFixed(decimals);
};

// 모델 목록
const MODEL_OPTIONS = [
  { value: 'WeightedEnsemble', label: 'WeightedEnsemble (AutoGluon)', inference: '8ms' },
  { value: 'XGBoost', label: 'XGBoost', inference: '5ms' },
  { value: 'LightGBM', label: 'LightGBM', inference: '3ms' },
  { value: 'LSTM', label: 'LSTM', inference: '15ms' },
];

// 재학습 단계명
const STAGE_LABELS = {
  data_prep: '데이터 전처리',
  training: '모델 학습',
  evaluation: '모델 평가',
  deploy: '배포',
};

export default function ModelsPanel({ auth, apiCall }) {
  const [mlflowData, setMlflowData] = useState([]);
  const [registeredModels, setRegisteredModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selecting, setSelecting] = useState(null);
  const [selectedModels, setSelectedModels] = useState({});
  const [message, setMessage] = useState(null);
  const [usingSample, setUsingSample] = useState(false);
  const [driftData, setDriftData] = useState(null);

  // 새 기능 상태
  const [activeModel, setActiveModel] = useState('WeightedEnsemble');
  const [learningRate, setLearningRate] = useState(0.05);
  const [maxDepth, setMaxDepth] = useState(6);
  const [retraining, setRetraining] = useState(false);
  const [retrainProgress, setRetrainProgress] = useState(0);
  const [retrainStage, setRetrainStage] = useState('');
  const [retrainResult, setRetrainResult] = useState(null);
  const [ensembleWeights, setEnsembleWeights] = useState({ xgboost: 45, lightgbm: 35, rf: 20 });
  const [ensembleResult, setEnsembleResult] = useState(null);
  const [ensembleLoading, setEnsembleLoading] = useState(false);
  const [abModelA, setAbModelA] = useState('WeightedEnsemble');
  const [abModelB, setAbModelB] = useState('XGBoost');
  const [abResult, setAbResult] = useState(null);
  const [abLoading, setAbLoading] = useState(false);
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const eventSourceRef = useRef(null);

  const SF_KEYWORDS = ['smart-factory', 'sf-ai', '고장', '설비', '생산량', '이상', '정비', '품질'];

  const fetchMLflowData = useCallback(async (reset = false) => {
    if (reset) {
      setMlflowData([]);
      setRegisteredModels([]);
    }
    setLoading(true);
    let gotRealData = false;

    try {
      const expRes = await apiCall({
        endpoint: '/api/mlflow/experiments',
        auth,
        timeoutMs: 10000,
      });
      if (expRes?.status === 'success' && expRes.data?.length > 0) {
        const sfExps = expRes.data.filter(exp => {
          const name = exp.name.toLowerCase();
          return SF_KEYWORDS.some(kw => name.includes(kw.toLowerCase()));
        });
        if (sfExps.length > 0) {
          setMlflowData(sfExps);
          gotRealData = true;
        }
      }
    } catch (e) {
      console.log('MLflow 실험 API fallback');
    }

    try {
      const modelsRes = await apiCall({
        endpoint: '/api/mlflow/models',
        auth,
        timeoutMs: 10000,
      });
      if (modelsRes?.status === 'success' && modelsRes.data?.length > 0) {
        setRegisteredModels(modelsRes.data);
        gotRealData = true;
      }
    } catch (e) {
      console.log('MLflow 모델 API fallback');
    }

    if (!gotRealData) {
      setMlflowData([]);
      setRegisteredModels([]);
      setUsingSample(true);
    } else {
      setUsingSample(false);
    }

    setLoading(false);
  }, [apiCall, auth]);

  const fetchDriftData = useCallback(async () => {
    try {
      const res = await apiCall({
        endpoint: '/api/models/drift',
        auth,
        timeoutMs: 10000,
      });
      if (res?.status === 'success' && res.data) {
        setDriftData(res.data);
      }
    } catch (e) {
      console.log('Drift API not available');
    }
  }, [apiCall, auth]);

  const fetchVersions = useCallback(async () => {
    setVersionsLoading(true);
    try {
      const res = await apiCall({
        endpoint: '/api/models/versions',
        auth,
        timeoutMs: 10000,
      });
      if (res?.status === 'success' && res.data) {
        setVersions(res.data);
      }
    } catch (e) {
      console.log('Versions API not available');
    }
    setVersionsLoading(false);
  }, [apiCall, auth]);

  useEffect(() => {
    if (!auth) return;
    async function initLoad() {
      const [selectedRes] = await Promise.all([
        apiCall({ endpoint: '/api/mlflow/models/selected', auth, timeoutMs: 5000 }).catch(() => null),
        fetchMLflowData(),
        fetchDriftData(),
        fetchVersions(),
      ]);
      if (selectedRes?.status === 'success' && selectedRes.data) {
        setSelectedModels(selectedRes.data);
      }
    }
    initLoad();
  }, [auth, apiCall, fetchMLflowData, fetchDriftData, fetchVersions]);

  // SSE cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const formatTimestamp = (ts) => {
    if (!ts) return '-';
    return new Date(ts).toLocaleString('ko-KR');
  };

  const handleSelectModel = async (modelName, version) => {
    const modelKey = `${modelName}-${version}`;
    setSelecting(modelKey);
    setMessage(null);

    try {
      const res = await apiCall({
        endpoint: '/api/mlflow/models/select',
        auth,
        method: 'POST',
        data: { model_name: modelName, version: String(version) },
        timeoutMs: 30000,
      });
      setSelecting(null);

      if (res?.status === 'success') {
        setSelectedModels(prev => ({ ...prev, [modelName]: version }));
        setMessage({ type: 'success', text: res.message || `${modelName} v${version} 모델이 로드되었습니다` });
      } else {
        setMessage({ type: 'error', text: res?.message || '모델 로드 실패' });
      }
    } catch (e) {
      setSelecting(null);
      setMessage({ type: 'error', text: `${modelName} 모델 선택 실패` });
    }

    setTimeout(() => setMessage(null), 5000);
  };

  // AI Model Control - 모델 적용
  const handleApplyModel = async () => {
    setSelecting('applying');
    try {
      const res = await apiCall({
        endpoint: '/api/mlflow/models/select',
        auth,
        method: 'POST',
        data: { model_name: activeModel, version: '1' },
        timeoutMs: 30000,
      });
      if (res?.status === 'success') {
        setMessage({ type: 'success', text: `${activeModel} 모델이 적용되었습니다` });
      } else {
        setMessage({ type: 'error', text: res?.message || '모델 적용 실패' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: '모델 적용 실패' });
    }
    setSelecting(null);
    setTimeout(() => setMessage(null), 5000);
  };

  // 재학습 SSE
  const handleRetrain = () => {
    if (retraining) return;
    setRetraining(true);
    setRetrainProgress(0);
    setRetrainStage('data_prep');
    setRetrainResult(null);

    const base = typeof window !== 'undefined' ? (window.location.origin) : '';
    const url = `${base}/api/models/retrain`;

    // Basic auth header via URL not supported by EventSource, use fetch SSE instead
    const authHeader = auth ? 'Basic ' + btoa(`${auth.username}:${auth.password}`) : '';

    fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: activeModel,
        learning_rate: learningRate,
        max_depth: maxDepth,
      }),
    }).then(async (response) => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.stage) {
                setRetrainProgress(data.progress || 0);
                setRetrainStage(data.stage);
              }
              if (data.status === 'success' && data.metrics) {
                setRetrainResult(data);
                setRetraining(false);
                fetchVersions();
              }
            } catch (e) {
              // ignore parse errors
            }
          }
        }
      }
    }).catch((e) => {
      console.log('Retrain SSE error:', e);
      setRetraining(false);
      setMessage({ type: 'error', text: '재학습 연결 실패' });
      setTimeout(() => setMessage(null), 5000);
    });
  };

  // 앙상블 가중치 조정 (합계 100 제약)
  const handleEnsembleChange = (key, value) => {
    const numVal = Number(value);
    const others = Object.entries(ensembleWeights).filter(([k]) => k !== key);
    const othersTotal = others.reduce((s, [, v]) => s + v, 0);
    const remaining = 100 - numVal;

    if (othersTotal === 0) {
      const newWeights = { ...ensembleWeights, [key]: numVal };
      const perOther = Math.round(remaining / others.length);
      others.forEach(([k], i) => {
        newWeights[k] = i === others.length - 1 ? remaining - perOther * (others.length - 1) : perOther;
      });
      setEnsembleWeights(newWeights);
    } else {
      const newWeights = { [key]: numVal };
      others.forEach(([k, v], i) => {
        if (i === others.length - 1) {
          newWeights[k] = Math.max(0, remaining - others.slice(0, -1).reduce((s, [ok]) => s + (newWeights[ok] || 0), 0));
        } else {
          newWeights[k] = Math.max(0, Math.round((v / othersTotal) * remaining));
        }
      });
      setEnsembleWeights(newWeights);
    }
  };

  // 앙상블 적용
  const handleEnsembleApply = async () => {
    setEnsembleLoading(true);
    try {
      const weights = {};
      Object.entries(ensembleWeights).forEach(([k, v]) => {
        weights[k] = v / 100;
      });
      const res = await apiCall({
        endpoint: '/api/models/ensemble',
        auth,
        method: 'POST',
        data: { weights },
        timeoutMs: 10000,
      });
      if (res?.status === 'success') {
        setEnsembleResult(res);
        setMessage({ type: 'success', text: '앙상블 가중치가 적용되었습니다' });
      } else {
        setMessage({ type: 'error', text: res?.message || '앙상블 적용 실패' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: '앙상블 적용 실패' });
    }
    setEnsembleLoading(false);
    setTimeout(() => setMessage(null), 5000);
  };

  // A/B 테스트
  const handleABTest = async () => {
    if (abModelA === abModelB) {
      setMessage({ type: 'error', text: '서로 다른 모델을 선택해주세요' });
      setTimeout(() => setMessage(null), 3000);
      return;
    }
    setAbLoading(true);
    setAbResult(null);
    try {
      const res = await apiCall({
        endpoint: '/api/models/ab-test',
        auth,
        method: 'POST',
        data: { model_a: abModelA, model_b: abModelB },
        timeoutMs: 10000,
      });
      if (res?.status === 'success') {
        setAbResult(res);
      } else {
        setMessage({ type: 'error', text: 'A/B 테스트 실패' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'A/B 테스트 실패' });
    }
    setAbLoading(false);
    setTimeout(() => setMessage(null), 5000);
  };

  const handleRefresh = () => {
    fetchMLflowData(true);
    fetchDriftData();
    fetchVersions();
  };

  // 현재 모델 상태 계산
  const activeModelInfo = useMemo(() => {
    if (!registeredModels.length) return null;

    const activeM = registeredModels.find(m =>
      selectedModels[m.name] !== undefined
    ) || registeredModels[0];

    const totalVersions = registeredModels.reduce((sum, m) => sum + (m.versions?.length || 0), 0);

    const latestRmse = driftData?.rmse_trend?.length
      ? driftData.rmse_trend[driftData.rmse_trend.length - 1]?.rmse
      : null;

    const threshold = driftData?.threshold || 0.003;
    let status = '정상';
    if (latestRmse !== null && latestRmse > threshold) {
      status = latestRmse > threshold * 2 ? '위험' : '주의';
    }

    return {
      name: activeM.name,
      totalVersions,
      latestRmse,
      status,
      threshold,
    };
  }, [registeredModels, selectedModels, driftData]);

  // threshold 초과 영역 계산
  const thresholdExceeded = useMemo(() => {
    if (!driftData?.rmse_trend || !driftData.threshold) return [];
    const areas = [];
    let start = null;
    for (const point of driftData.rmse_trend) {
      if (point.rmse > driftData.threshold) {
        if (!start) start = point.date;
      } else if (start) {
        areas.push({ x1: start, x2: point.date });
        start = null;
      }
    }
    if (start) {
      areas.push({ x1: start, x2: driftData.rmse_trend[driftData.rmse_trend.length - 1].date });
    }
    return areas;
  }, [driftData]);

  return (
    <div>
      <SectionHeader
        title="MLOps 대시보드"
        subtitle="타깃: 지시압연속도 변화량(Δ) · AI 모델 제어 · 하이퍼파라미터 튜닝 · 앙상블 · A/B 테스트 · 드리프트 모니터링"
        right={
          <div className="flex items-center gap-2">
            <span className={`rounded-full border-2 px-2 py-1 text-[10px] font-black ${
              usingSample
                ? 'border-amber-400/50 bg-amber-50 text-amber-700'
                : 'border-green-400/50 bg-green-50 text-green-700'
            }`}>
              {usingSample ? 'SAMPLE' : 'LIVE'}
            </span>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="rounded-full border-2 border-sf-orange/20 bg-white/80 p-1.5 hover:bg-sf-beige transition disabled:opacity-50"
            >
              <RefreshCw size={14} className={`text-sf-brown ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        }
      />

      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className={`mb-4 p-3 rounded-2xl flex items-center gap-2 text-sm ${
            message.type === 'success'
              ? 'bg-green-50 border-2 border-green-200 text-green-700'
              : 'bg-red-50 border-2 border-red-200 text-red-700'
          }`}
        >
          {message.type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
          {message.text}
        </motion.div>
      )}

      {/* ============================================================ */}
      {/* 1. AI Model Control */}
      {/* ============================================================ */}
      <motion.div variants={cardVariants} initial="hidden" animate="visible" className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Brain size={18} className="text-sf-orange" />
          <h3 className="text-sm font-black text-sf-brown">AI Model Control</h3>
        </div>
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1">
              <label className="text-xs font-bold text-sf-brown/60 mb-1 block">활성 모델 선택</label>
              <select
                value={activeModel}
                onChange={(e) => setActiveModel(e.target.value)}
                className="w-full sm:w-64 rounded-xl border-2 border-sf-orange/20 bg-white px-3 py-2 text-sm font-semibold text-sf-brown focus:outline-none focus:border-sf-orange/50 transition"
              >
                {MODEL_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleApplyModel}
              disabled={selecting === 'applying'}
              className="px-5 py-2 rounded-xl bg-sf-beige text-sf-brown text-sm font-bold shadow hover:shadow-md transition disabled:opacity-50"
            >
              {selecting === 'applying' ? '적용 중...' : '적용'}
            </button>
          </div>
        </div>
      </motion.div>

      {/* ============================================================ */}
      {/* 2. 하이퍼파라미터 튜닝 */}
      {/* ============================================================ */}
      <motion.div variants={cardVariants} initial="hidden" animate="visible" className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Sliders size={18} className="text-sf-orange" />
          <h3 className="text-sm font-black text-sf-brown">하이퍼파라미터 튜닝</h3>
        </div>
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-5">
            {/* Learning Rate */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-bold text-sf-brown/60">Learning Rate</label>
                <span className="text-xs font-mono font-bold text-sf-orange">{learningRate.toFixed(3)}</span>
              </div>
              <input
                type="range"
                min="0.001"
                max="0.3"
                step="0.001"
                value={learningRate}
                onChange={(e) => setLearningRate(parseFloat(e.target.value))}
                className="w-full h-2 rounded-full appearance-none cursor-pointer accent-orange-500"
                style={{ accentColor: '#f97316' }}
              />
              <div className="flex justify-between text-[10px] text-sf-brown/40 mt-1">
                <span>0.001</span>
                <span>0.3</span>
              </div>
            </div>
            {/* Max Depth */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-bold text-sf-brown/60">Max Depth</label>
                <span className="text-xs font-mono font-bold text-sf-orange">{maxDepth}</span>
              </div>
              <input
                type="range"
                min="3"
                max="15"
                step="1"
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value))}
                className="w-full h-2 rounded-full appearance-none cursor-pointer"
                style={{ accentColor: '#f97316' }}
              />
              <div className="flex justify-between text-[10px] text-sf-brown/40 mt-1">
                <span>3</span>
                <span>15</span>
              </div>
            </div>
          </div>

          {/* Start Retraining */}
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={handleRetrain}
              disabled={retraining}
              className="px-5 py-2.5 rounded-xl bg-sf-beige text-sf-brown text-sm font-bold shadow hover:shadow-md transition disabled:opacity-50 flex items-center gap-2"
            >
              {retraining ? (
                <RefreshCw size={14} className="animate-spin" />
              ) : (
                <Play size={14} />
              )}
              {retraining ? '학습 중...' : 'Start Retraining'}
            </button>
            {retraining && (
              <span className="text-xs text-sf-brown/60">
                {STAGE_LABELS[retrainStage] || retrainStage}
              </span>
            )}
          </div>

          {/* 프로그레스바 */}
          {(retraining || retrainResult) && (
            <div className="mb-4">
              <div className="flex justify-between text-[10px] text-sf-brown/60 mb-1">
                <span>{STAGE_LABELS[retrainStage] || (retrainResult ? '완료' : '')}</span>
                <span>{retrainResult ? '100' : Math.round(retrainProgress)}%</span>
              </div>
              <div className="h-3 rounded-full bg-gray-100 overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-sf-orange to-sf-yellow"
                  initial={{ width: 0 }}
                  animate={{ width: `${retrainResult ? 100 : retrainProgress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              {/* 단계 표시 */}
              <div className="flex justify-between mt-2">
                {['data_prep', 'training', 'evaluation', 'deploy'].map((stage) => {
                  const stageStart = { data_prep: 0, training: 25, evaluation: 70, deploy: 90 }[stage];
                  const pct = retrainResult ? 100 : retrainProgress;
                  const active = pct >= stageStart;
                  return (
                    <div key={stage} className="flex flex-col items-center">
                      <div className={`w-2 h-2 rounded-full ${active ? 'bg-sf-orange' : 'bg-gray-300'}`} />
                      <span className={`text-[9px] mt-0.5 ${active ? 'text-sf-brown font-bold' : 'text-sf-brown/40'}`}>
                        {STAGE_LABELS[stage]}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 재학습 결과 */}
          <AnimatePresence>
            {retrainResult && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3"
              >
                {[
                  { label: 'RMSE', value: retrainResult.metrics.rmse, icon: TrendingUp },
                  { label: 'R\u00B2', value: retrainResult.metrics.r2, icon: Award },
                  { label: 'MAE', value: retrainResult.metrics.mae, icon: Activity },
                  { label: '소요 시간', value: retrainResult.duration_sec, unit: 's', decimals: 1, icon: Clock },
                ].map(({ label, value, unit, decimals, icon: Icon }) => (
                  <motion.div
                    key={label}
                    variants={cardVariants}
                    initial="hidden"
                    animate="visible"
                    className="rounded-xl border-2 border-green-200 bg-green-50/50 p-4"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon size={14} className="text-green-600" />
                      <span className="text-[10px] font-bold text-green-700">{label}</span>
                    </div>
                    <p className="text-lg font-black text-green-800">
                      <AnimatedNumber value={value} decimals={decimals || 4} />{unit || ''}
                    </p>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* ============================================================ */}
      {/* 3. 앙상블 가중치 관리 */}
      {/* ============================================================ */}
      <motion.div variants={cardVariants} initial="hidden" animate="visible" className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Scale size={18} className="text-sf-orange" />
          <h3 className="text-sm font-black text-sf-brown">앙상블 가중치 관리</h3>
        </div>
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="space-y-4 mb-5">
            {[
              { key: 'xgboost', label: 'XGBoost' },
              { key: 'lightgbm', label: 'LightGBM' },
              { key: 'rf', label: 'RandomForest' },
            ].map(({ key, label }) => (
              <div key={key}>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-bold text-sf-brown">{label}</label>
                  <span className="text-xs font-mono font-bold text-sf-orange">{ensembleWeights[key]}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={ensembleWeights[key]}
                  onChange={(e) => handleEnsembleChange(key, e.target.value)}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer"
                  style={{ accentColor: '#f97316' }}
                />
              </div>
            ))}
            <div className="flex justify-between items-center pt-2 border-t border-sf-orange/10">
              <span className="text-xs text-sf-brown/60">합계</span>
              <span className={`text-xs font-bold ${
                Object.values(ensembleWeights).reduce((s, v) => s + v, 0) === 100
                  ? 'text-green-600' : 'text-red-500'
              }`}>
                {Object.values(ensembleWeights).reduce((s, v) => s + v, 0)}%
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleEnsembleApply}
              disabled={ensembleLoading}
              className="px-5 py-2 rounded-xl bg-sf-beige text-sf-brown text-sm font-bold shadow hover:shadow-md transition disabled:opacity-50"
            >
              {ensembleLoading ? '적용 중...' : '적용'}
            </button>
            {ensembleResult && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-xs text-green-600 font-bold"
              >
                예상 성능 개선: +{ensembleResult.improvement_pct}%
              </motion.span>
            )}
          </div>

          {/* 앙상블 결과 메트릭 */}
          <AnimatePresence>
            {ensembleResult?.ensemble_metrics && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3"
              >
                {[
                  { label: 'RMSE', value: ensembleResult.ensemble_metrics.rmse },
                  { label: 'R\u00B2', value: ensembleResult.ensemble_metrics.r2 },
                  { label: 'MAE', value: ensembleResult.ensemble_metrics.mae },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-xl border border-sf-orange/20 bg-sf-beige/20 p-3 text-center">
                    <p className="text-[10px] text-sf-brown/60 font-bold">{label}</p>
                    <p className="text-lg font-black text-sf-brown">
                      <AnimatedNumber value={value} />
                    </p>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* ============================================================ */}
      {/* 4. A/B 테스트 비교 */}
      {/* ============================================================ */}
      <motion.div variants={cardVariants} initial="hidden" animate="visible" className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Beaker size={18} className="text-sf-orange" />
          <h3 className="text-sm font-black text-sf-brown">A/B 테스트 비교</h3>
        </div>
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4 mb-5">
            <div className="flex-1">
              <label className="text-xs font-bold text-sf-brown/60 mb-1 block">Model A</label>
              <select
                value={abModelA}
                onChange={(e) => setAbModelA(e.target.value)}
                className="w-full rounded-xl border-2 border-sf-orange/20 bg-white px-3 py-2 text-sm font-semibold text-sf-brown focus:outline-none focus:border-sf-orange/50 transition"
              >
                {MODEL_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <span className="text-sf-brown/40 font-black text-lg hidden sm:block pb-1">vs</span>
            <div className="flex-1">
              <label className="text-xs font-bold text-sf-brown/60 mb-1 block">Model B</label>
              <select
                value={abModelB}
                onChange={(e) => setAbModelB(e.target.value)}
                className="w-full rounded-xl border-2 border-sf-orange/20 bg-white px-3 py-2 text-sm font-semibold text-sf-brown focus:outline-none focus:border-sf-orange/50 transition"
              >
                {MODEL_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleABTest}
              disabled={abLoading}
              className="px-5 py-2 rounded-xl bg-sf-beige text-sf-brown text-sm font-bold shadow hover:shadow-md transition disabled:opacity-50"
            >
              {abLoading ? '비교 중...' : '비교'}
            </button>
          </div>

          {/* A/B 결과 */}
          <AnimatePresence>
            {abResult && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { label: 'A', data: abResult.model_a },
                    { label: 'B', data: abResult.model_b },
                  ].map(({ label, data }) => {
                    const isWinner = data.model === abResult.recommendation;
                    return (
                      <motion.div
                        key={label}
                        variants={cardVariants}
                        initial="hidden"
                        animate="visible"
                        className={`rounded-xl p-4 border-2 ${
                          isWinner
                            ? 'border-green-400 bg-green-50/50'
                            : 'border-gray-200 bg-gray-50/50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-black text-sf-brown">{data.model}</span>
                          {isWinner && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-green-500 text-white">
                              WINNER
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { k: 'RMSE', v: data.rmse },
                            { k: 'MAE', v: data.mae },
                            { k: 'R\u00B2', v: data.r2 },
                            { k: 'Inference', v: data.inference_ms, unit: 'ms', dec: 1 },
                          ].map(({ k, v, unit, dec }) => (
                            <div key={k} className="text-center p-2 rounded-lg bg-white/60">
                              <p className="text-[10px] text-sf-brown/60 font-bold">{k}</p>
                              <p className="text-sm font-black text-sf-brown">
                                {v.toFixed(dec || 4)}{unit || ''}
                              </p>
                            </div>
                          ))}
                        </div>
                        {isWinner && (
                          <button className="w-full mt-3 px-4 py-2 rounded-lg bg-green-500 text-white text-xs font-bold hover:bg-green-600 transition">
                            Deploy
                          </button>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
                <p className="text-xs text-sf-brown/60 mt-3 text-center">
                  {abResult.reason} (테스트 샘플: {abResult.test_samples}건)
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* ============================================================ */}
      {/* 5. 버전 이력 테이블 */}
      {/* ============================================================ */}
      <motion.div variants={cardVariants} initial="hidden" animate="visible" className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <GitBranch size={18} className="text-sf-orange" />
          <h3 className="text-sm font-black text-sf-brown">모델 버전 이력</h3>
        </div>
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 shadow-sm backdrop-blur overflow-hidden">
          {versionsLoading ? (
            <div className="p-8 text-center text-sm text-sf-brown/50">로딩 중...</div>
          ) : versions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-sf-orange/10 bg-sf-beige/30">
                    <th className="text-left py-3 px-4 text-sf-brown font-bold text-xs">버전</th>
                    <th className="text-left py-3 px-4 text-sf-brown font-bold text-xs">모델명</th>
                    <th className="text-left py-3 px-4 text-sf-brown font-bold text-xs">Stage</th>
                    <th className="text-center py-3 px-4 text-sf-brown font-bold text-xs">RMSE</th>
                    <th className="text-center py-3 px-4 text-sf-brown font-bold text-xs">R2</th>
                    <th className="text-left py-3 px-4 text-sf-brown font-bold text-xs">생성일</th>
                    <th className="text-left py-3 px-4 text-sf-brown font-bold text-xs">상태</th>
                    <th className="text-center py-3 px-4 text-sf-brown font-bold text-xs">작업</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((v, i) => (
                    <tr key={`${v.model_name}-${v.version}-${i}`} className="border-b border-sf-orange/5 hover:bg-sf-beige/30 transition">
                      <td className="py-3 px-4 font-semibold text-sf-brown">v{v.version}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <Brain size={14} className="text-sf-orange" />
                          <span className="font-bold text-sf-brown">{v.model_name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                          v.stage === 'Production' ? 'bg-green-100 text-green-700 border border-green-300' :
                          v.stage === 'Staging' ? 'bg-blue-100 text-blue-700 border border-blue-300' :
                          'bg-gray-100 text-gray-500'
                        }`}>
                          {v.stage || 'Archived'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-xs text-sf-brown">
                        {v.metrics?.rmse?.toFixed(4) || '-'}
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-xs text-sf-brown">
                        {v.metrics?.r2?.toFixed(4) || '-'}
                      </td>
                      <td className="py-3 px-4 text-xs text-sf-brown/60">
                        {formatTimestamp(v.created_at)}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                          v.status === 'READY' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {v.status || 'READY'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            className="text-[10px] px-2 py-1 rounded-lg border border-sf-orange/30 text-sf-brown hover:bg-sf-beige transition font-bold"
                            title="Rollback"
                          >
                            <RotateCcw size={12} />
                          </button>
                          <button
                            className="text-[10px] px-2 py-1 rounded-lg border border-sf-orange/30 text-sf-brown hover:bg-sf-beige transition font-bold"
                            title="Export"
                          >
                            <Download size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-sf-brown/50">
              버전 이력이 없습니다.
            </div>
          )}
        </div>
      </motion.div>

      {/* ============================================================ */}
      {/* 기존 유지: 현재 모델 상태 카드 */}
      {/* ============================================================ */}
      {activeModelInfo && (
        <motion.div variants={cardVariants} initial="hidden" animate="visible" className="mb-6 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <div className="flex items-center gap-2 mb-2">
              <Brain size={16} className="text-sf-orange" />
              <span className="text-xs text-sf-brown/60">활성 모델</span>
            </div>
            <p className="text-sm font-black text-sf-brown truncate">{activeModelInfo.name}</p>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <div className="flex items-center gap-2 mb-2">
              <Layers size={16} className="text-sf-orange" />
              <span className="text-xs text-sf-brown/60">총 모델 버전</span>
            </div>
            <p className="text-2xl font-black text-sf-brown">{activeModelInfo.totalVersions}</p>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp size={16} className="text-sf-orange" />
              <span className="text-xs text-sf-brown/60">현재 RMSE</span>
            </div>
            <p className="text-2xl font-black text-sf-brown">
              {activeModelInfo.latestRmse !== null ? activeModelInfo.latestRmse.toFixed(4) : '-'}
            </p>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <div className="flex items-center gap-2 mb-2">
              <Shield size={16} className="text-sf-orange" />
              <span className="text-xs text-sf-brown/60">모델 상태</span>
            </div>
            <div className="mt-1">
              <StatusBadge status={activeModelInfo.status} size="lg" />
            </div>
          </div>
        </motion.div>
      )}

      {/* ============================================================ */}
      {/* 기존 유지: 성능 드리프트 모니터링 (RMSE 추이) */}
      {/* ============================================================ */}
      {driftData?.rmse_trend?.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-sf-orange" />
              <h3 className="text-sm font-black text-sf-brown">성능 드리프트 모니터링</h3>
            </div>
            <StatusBadge
              status={
                driftData.rmse_trend[driftData.rmse_trend.length - 1]?.rmse > driftData.threshold
                  ? '주의' : '정상'
              }
              size="lg"
            />
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <p className="text-xs text-sf-brown/60 mb-3">30일간 RMSE 추이 (Threshold: {driftData.threshold})</p>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={driftData.rmse_trend} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: '#78716c' }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#78716c' }}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => v.toFixed(3)}
                />
                <Tooltip content={<ChartTooltip />} />
                {thresholdExceeded.map((area, i) => (
                  <ReferenceArea
                    key={i}
                    x1={area.x1}
                    x2={area.x2}
                    fill="#fecaca"
                    fillOpacity={0.3}
                  />
                ))}
                <ReferenceLine
                  y={driftData.threshold}
                  stroke="#ef4444"
                  strokeDasharray="6 3"
                  strokeWidth={2}
                  label={{ value: 'Threshold', position: 'right', fill: '#ef4444', fontSize: 10 }}
                />
                <Line
                  type="monotone"
                  dataKey="rmse"
                  name="RMSE"
                  stroke="#f97316"
                  strokeWidth={2}
                  dot={{ r: 2, fill: '#f97316' }}
                  activeDot={{ r: 5, fill: '#ea580c' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 기존 유지: Feature Drift (PSI) 모니터링 */}
      {/* ============================================================ */}
      {driftData?.feature_psi?.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={18} className="text-sf-orange" />
            <h3 className="text-sm font-black text-sf-brown">Feature Drift (PSI)</h3>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={driftData.feature_psi}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 80, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 10, fill: '#78716c' }}
                      tickFormatter={(v) => v.toFixed(2)}
                    />
                    <YAxis
                      dataKey="feature"
                      type="category"
                      tick={{ fontSize: 10, fill: '#78716c' }}
                      width={75}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="psi" name="PSI" radius={[0, 4, 4, 0]}>
                      {driftData.feature_psi.map((entry, index) => (
                        <Cell key={index} fill={PSI_COLORS[entry.status] || '#9ca3af'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-bold text-sf-brown/60 mb-3">Feature별 상태</p>
                {driftData.feature_psi.map((f, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-xl bg-sf-beige/30">
                    <span className="text-xs font-semibold text-sf-brown">{f.feature}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-sf-brown/60 font-mono">{f.psi.toFixed(4)}</span>
                      <StatusBadge status={f.status} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 기존 유지: 예측 오차 분포 히스토그램 */}
      {/* ============================================================ */}
      {driftData?.error_distribution?.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle size={18} className="text-sf-orange" />
            <h3 className="text-sm font-black text-sf-brown">예측 오차 분포</h3>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
            <p className="text-xs text-sf-brown/60 mb-3">0 중심 정규분포 형태가 이상적 (바이어스 확인)</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={driftData.error_distribution} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="bin"
                  tick={{ fontSize: 10, fill: '#78716c' }}
                />
                <YAxis tick={{ fontSize: 10, fill: '#78716c' }} />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine x="0" stroke="#78716c" strokeDasharray="4 2" />
                <Bar dataKey="count" name="빈도" fill="#f97316" radius={[4, 4, 0, 0]} fillOpacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 기존 유지: 실험 기록 */}
      {/* ============================================================ */}
      <div className="flex items-center gap-2 mb-4">
        <FlaskConical size={18} className="text-sf-orange" />
        <h3 className="text-sm font-black text-sf-brown">실험 기록</h3>
      </div>

      {mlflowData.length ? mlflowData.map((exp) => (
        <div key={exp.experiment_id} className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur mb-4">
          <div className="flex justify-between items-center mb-4">
            <span className="font-bold text-sf-brown">{exp.name}</span>
            <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${
              exp.lifecycle_stage === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
            }`}>
              {exp.lifecycle_stage}
            </span>
          </div>

          {exp.runs && exp.runs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-sf-orange/10">
                    <th className="text-left py-2 px-2 text-sf-brown font-bold text-xs">Run Name</th>
                    <th className="text-left py-2 px-2 text-sf-brown font-bold text-xs">Status</th>
                    <th className="text-left py-2 px-2 text-sf-brown font-bold text-xs">시작 시간</th>
                    <th className="text-left py-2 px-2 text-sf-brown font-bold text-xs">Metrics</th>
                    <th className="text-left py-2 px-2 text-sf-brown font-bold text-xs">Params</th>
                  </tr>
                </thead>
                <tbody>
                  {exp.runs.map((run) => (
                    <tr key={run.run_id} className="border-b border-sf-orange/5 hover:bg-sf-beige/30 transition">
                      <td className="py-3 px-2 font-semibold text-sf-brown">
                        {run.run_name || run.run_id.slice(0, 8)}
                      </td>
                      <td className="py-3 px-2">
                        <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${
                          run.status === 'FINISHED' ? 'bg-green-100 text-green-700' :
                          run.status === 'RUNNING' ? 'bg-blue-100 text-blue-700 animate-pulse' :
                          run.status === 'error' ? 'bg-red-100 text-red-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {run.status}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-sf-brown/60 text-xs">
                        {formatTimestamp(run.start_time)}
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(run.metrics || {}).map(([k, v]) => (
                            <span key={k} className="text-[10px] bg-sf-yellow/30 text-sf-brown px-2 py-0.5 rounded-full font-semibold">
                              {k}: {typeof v === 'number' ? v.toFixed(4) : v}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(run.params || {}).slice(0, 3).map(([k, v]) => (
                            <span key={k} className="text-[10px] bg-sf-beige text-sf-brown/70 px-2 py-0.5 rounded-full">
                              {k}: {v}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-sm text-sf-brown/50 py-4 text-center">
              실험 기록이 없습니다.
            </div>
          )}
        </div>
      )) : (
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-8 text-center">
          <FlaskConical size={32} className="mx-auto mb-3 text-sf-brown/30" />
          <p className="text-sm text-sf-brown/60">MLflow 실험이 없습니다.</p>
          <p className="text-xs text-sf-brown/40 mt-1">
            노트북을 실행하여 모델을 학습하세요.
          </p>
        </div>
      )}
    </div>
  );
}
