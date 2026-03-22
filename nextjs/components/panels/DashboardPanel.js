// components/panels/DashboardPanel.js
// 스마트팩토리 AI 플랫폼 - 제조 대시보드 패널 (Recharts 버전)

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { usePageVisibility, usePolling } from '@/components/panels/hooks/usePageVisibility';
import { motion, AnimatePresence } from 'framer-motion';
import KpiCard from '@/components/KpiCard';
import EmptyState from '@/components/EmptyState';
import { SkeletonCard } from '@/components/Skeleton';
import {
  Wrench, Factory, Settings, BarChart3, RefreshCw,
  AlertTriangle, Zap, ArrowUpRight, Brain, Target,
  Activity, Clock, ChevronDown,
  X, ArrowUp, ArrowDown
} from 'lucide-react';
import SectionHeader from '@/components/SectionHeader';
import CustomTooltip from '@/components/common/CustomTooltip';
import {
  Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Line, LineChart, ReferenceDot
} from 'recharts';

// ─── 헬퍼 컴포넌트 ───

// 숫자 부드러운 보간 애니메이션
const AnimatedValue = memo(function AnimatedValue({ value, decimals = 1, className, suffix = '' }) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);

  useEffect(() => {
    const prev = prevRef.current;
    const diff = value - prev;
    if (Math.abs(diff) < 0.001) {
      setDisplay(value);
      prevRef.current = value;
      return;
    }
    let frame = 0;
    const totalFrames = 10;
    const id = setInterval(() => {
      frame++;
      setDisplay(prev + diff * (frame / totalFrames));
      if (frame >= totalFrames) {
        clearInterval(id);
        prevRef.current = value;
      }
    }, 30);
    return () => clearInterval(id);
  }, [value]);

  return <span className={className}>{display.toFixed(decimals)}{suffix}</span>;
});

// LIVE 인디케이터
const LiveIndicator = memo(() => {
  const [now, setNow] = useState(new Date());
  const clockVisible = usePageVisibility();
  useEffect(() => {
    if (!clockVisible) return;
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, [clockVisible]);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border-2 border-green-400/50 bg-green-50 px-2.5 py-1 text-[10px] font-black text-green-700">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
      </span>
      LIVE
      <span className="ml-0.5 font-mono text-green-600">
        {now.toLocaleTimeString('ko-KR', { hour12: false })}
      </span>
    </span>
  );
});

// 미니 스파크라인 (스탠드 카드 하단)
const MiniSparkline = memo(({ data = [], dataKey = 'value', color = '#1B6FF0' }) => {
  if (data.length < 2) return null;
  return (
    <ResponsiveContainer width={80} height={25}>
      <LineChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
});

// 섹션 fade-in 애니메이션 래퍼
const FadeInSection = memo(({ children, className = '', delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, margin: '-50px' }}
    transition={{ duration: 0.5, delay, ease: 'easeOut' }}
    className={className}
  >
    {children}
  </motion.div>
));

// 파이 차트용 커스텀 툴팁
// OEE 게이지 컴포넌트 (CSS 원형 progress)
const OeeGauge = memo(({ value = 0 }) => {
  const clampedValue = Math.min(100, Math.max(0, value));
  const color = clampedValue < 60 ? '#ef4444' : clampedValue < 85 ? '#f59e0b' : '#10b981';
  const bgColor = clampedValue < 60 ? 'bg-red-50' : clampedValue < 85 ? 'bg-amber-50' : 'bg-emerald-50';
  const circumference = 2 * Math.PI * 40;
  const strokeDashoffset = circumference - (clampedValue / 100) * circumference;

  return (
    <div className={`rounded-2xl border-2 border-sf-orange/20 ${bgColor} p-3 shadow-sm backdrop-blur transition-all duration-300 hover:shadow-lg hover:-translate-y-1`}>
      <div className="text-[10px] font-extrabold tracking-wide text-sf-brown/70 mb-1">OEE</div>
      <div className="flex items-center justify-center">
        <div className="relative w-14 h-14 flex-shrink-0">
          <svg className="w-14 h-14 -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" strokeWidth="10" />
            <circle
              cx="50" cy="50" r="40"
              fill="none"
              stroke={color}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              style={{ transition: 'stroke-dashoffset 1s ease' }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <AnimatedValue value={clampedValue} decimals={1} className="text-xs font-black text-sf-brown" />
          </div>
        </div>
      </div>
      <div className="text-center mt-1">
        <div className="text-[10px] font-semibold" style={{ color }}>
          {clampedValue < 60 ? '개선 필요' : clampedValue < 85 ? '보통' : '양호'}
        </div>
      </div>
    </div>
  );
});

// 미니 프로그레스 바
const MiniProgressBar = memo(({ value = 0, color = '#10b981' }) => (
  <div className="w-full h-1.5 rounded-full bg-gray-200 overflow-hidden">
    <div
      className="h-full rounded-full transition-all duration-500"
      style={{ width: `${Math.min(100, Math.max(0, value))}%`, backgroundColor: color }}
    />
  </div>
));

// 스탠드 상태 배지 (normal/warning/alarm)
const StandStatusBadge = memo(({ status }) => {
  const cfg = {
    normal: { emoji: '\u{1F7E2}', label: '정상', bg: 'bg-emerald-100', text: 'text-emerald-700' },
    warning: { emoji: '\u{1F7E1}', label: '주의', bg: 'bg-yellow-100', text: 'text-yellow-700' },
    alarm: { emoji: '\u{1F534}', label: '경보', bg: 'bg-red-100', text: 'text-red-700' },
  };
  const c = cfg[status] || cfg.normal;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${c.bg} ${c.text}`}>
      <span>{c.emoji}</span>{c.label}
    </span>
  );
});

// Load vs Speed 차트용 커스텀 툴팁
const LoadSpeedTooltip = memo(({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border-2 border-sf-orange/20 bg-white/95 px-3 py-2 shadow-lg backdrop-blur">
      <p className="text-[10px] font-bold text-sf-brown/70 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-xs font-semibold" style={{ color: p.color }}>
          {p.name}: {p.value?.toLocaleString()} {p.name.includes('하중') ? 'kN' : 'm/s'}
        </p>
      ))}
    </div>
  );
});

// ─── 스탠드 상세 모달 ───
const StandDetailModal = ({ standId, standName, apiCall, auth, onClose, equipment = 'FM-LINE1' }) => {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  // 0.25초 클라이언트 보간용 상태
  const [localSeries, setLocalSeries] = useState([]);
  const detailBaseRef = useRef(null);

  const loadDetail = useCallback(async () => {
    try {
      const res = await apiCall({ endpoint: `/api/stands/${standId}/detail?equipment=${equipment}`, auth, timeoutMs: 10000 });
      if (res) setDetail(res);
    } catch (e) {
      console.error('스탠드 상세 로드 실패:', e);
    } finally {
      setLoading(false);
    }
  }, [standId, apiCall, auth, equipment]);

  // 스탠드 상세 2초 폴링 (탭 비활성 시 완전 중단)
  usePolling(loadDetail, 2000, { immediate: true });

  // API에서 받은 최신 제어값을 기준으로 저장
  useEffect(() => {
    if (detail?.control_values) {
      detailBaseRef.current = detail.control_values;
    }
  }, [detail]);

  // 0.25초마다 보간값 생성 (탭 비활성 시 중단)
  const isVisible = usePageVisibility();
  useEffect(() => {
    if (!isVisible) return;
    const interval = setInterval(() => {
      const base = detailBaseRef.current;
      if (!base) return;
      const t = Date.now() / 1000;
      const noise = (Math.random() - 0.5) * 0.01;
      const wave = Math.sin(t * 1.2) * 0.005;
      setLocalSeries(prev => {
        const newPoint = {
          time: new Date().toLocaleTimeString('ko-KR', { hour12: false, fractionalSecondDigits: 1 }),
          setpoint: +(base.setpoint + wave).toFixed(3),
          actual: +(base.actual + wave + noise).toFixed(3),
          current: +(detail?.stand?.current + Math.sin(t) * detail?.stand?.current * 0.02 + (Math.random() - 0.5) * 5).toFixed(1),
        };
        return [...prev, newPoint].slice(-80);
      });
    }, 250);
    return () => clearInterval(interval);
  }, [detail, isVisible]);

  // Escape 키로 닫기
  useEffect(() => {
    const handleKeyDown = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const statusColor = {
    normal: 'bg-emerald-500',
    warning: 'bg-yellow-500',
    alarm: 'bg-red-500',
  };

  const timeSeries = detail?.time_series || [];
  const controls = detail?.control_values || detail?.controls || {};
  const standInfo = detail?.stand || {};
  const pieceInfo = detail?.piece_info || detail?.product || '';
  const hmdLoaded = detail?.hmd_loaded ?? detail?.hmd_status;
  const rollGap = detail?.roll_gap || standInfo?.roll_gap || {};

  // localSeries 최신값으로 제어값 카드 표시 (0.25초 보간)
  const latestLocal = localSeries.length > 0 ? localSeries[localSeries.length - 1] : null;
  const liveSetpoint = latestLocal?.setpoint ?? controls.setpoint ?? 0;
  const liveActual = latestLocal?.actual ?? controls.actual ?? 0;
  const delta = liveActual - liveSetpoint;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-w-2xl mx-4 rounded-3xl border-2 border-sf-orange/30 bg-white shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="p-5 bg-gradient-to-r from-sf-brown to-sf-brown/80 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl font-black">{standName || `Stand ${standId}`}</span>
              {(standInfo?.status || detail?.status) && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold text-white ${statusColor[standInfo?.status || detail?.status] || 'bg-gray-500'}`}>
                  {(standInfo?.status || detail?.status) === 'normal' ? '정상' : (standInfo?.status || detail?.status) === 'warning' ? '주의' : '경보'}
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center transition"
            >
              <X size={16} />
            </button>
          </div>
          {pieceInfo && (
            <div className="mt-1 text-xs opacity-80">제품: {typeof pieceInfo === 'object' ? pieceInfo.name || JSON.stringify(pieceInfo) : pieceInfo}</div>
          )}
        </div>

        {loading && !detail ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-4 border-sf-orange/30 border-t-sf-orange rounded-full animate-spin" />
          </div>
        ) : detail ? (
          <div className="p-5 space-y-5">
            {/* 제어값 4-카드 그리드 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl bg-blue-50 border border-blue-200 p-3 text-center">
                <div className="text-[10px] font-bold text-blue-500 mb-1">Setpoint</div>
                <div className="text-xl font-black text-blue-700">
                  <AnimatedValue value={liveSetpoint} decimals={2} />
                </div>
                <div className="text-[9px] text-blue-400">m/s</div>
              </div>
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-center">
                <div className="text-[10px] font-bold text-emerald-500 mb-1">Actual</div>
                <div className="text-xl font-black text-emerald-700">
                  <AnimatedValue value={liveActual} decimals={2} />
                </div>
                <div className="text-[9px] text-emerald-400">m/s</div>
              </div>
              <div className={`rounded-xl border p-3 text-center ${
                delta >= 0 ? 'bg-blue-50 border-blue-200' : 'bg-red-50 border-red-200'
              }`}>
                <div className="text-[10px] font-bold text-sf-brown/60 mb-1">Delta</div>
                <div className={`text-xl font-black flex items-center justify-center gap-1 ${
                  delta >= 0 ? 'text-blue-600' : 'text-red-600'
                }`}>
                  {delta >= 0 ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
                  <AnimatedValue value={Math.abs(delta)} decimals={3} />
                </div>
                <div className="text-[9px] text-sf-brown/40">m/s</div>
              </div>
              <div className="rounded-xl bg-purple-50 border border-purple-200 p-3 text-center">
                <div className="text-[10px] font-bold text-purple-500 mb-1">AI 추천</div>
                <div className="text-xl font-black text-purple-700">
                  <AnimatedValue value={controls.ai_recommendation ?? 0} decimals={2} />
                </div>
                <button className="mt-1 px-3 py-0.5 rounded-full bg-purple-500 text-white text-[9px] font-bold hover:bg-purple-600 transition">
                  적용
                </button>
              </div>
            </div>

            {/* 실시간 차트: localSeries (0.25초 보간) 또는 time_series */}
            {(localSeries.length > 0 || timeSeries.length > 0) && (
              <div className="rounded-xl border border-sf-orange/20 bg-white p-4">
                <div className="text-xs font-black text-sf-brown mb-3">실시간 추이 (20초, 0.25s 갱신)</div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={localSeries.length > 0 ? localSeries : timeSeries} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#999' }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 9, fill: '#999' }} />
                    <Tooltip
                      contentStyle={{ fontSize: 11, borderRadius: 8 }}
                      labelStyle={{ fontWeight: 'bold' }}
                    />
                    <Line type="monotone" dataKey="current" name="전류(A)" stroke="#1B6FF0" strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="actual" name="Actual(m/s)" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="setpoint" name="Setpoint" stroke="#F97316" strokeWidth={1.5} strokeDasharray="5 5" dot={false} isAnimationActive={false} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: 10 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Roll Gap + HMD */}
            <div className="grid grid-cols-2 gap-3">
              {(rollGap.ws !== undefined || rollGap.ds !== undefined || rollGap.h !== undefined) && (
                <div className="rounded-xl bg-sf-cream/50 border border-sf-orange/15 p-3">
                  <div className="text-[10px] font-bold text-sf-brown/60 mb-2">Roll Gap</div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                      <div className="text-[9px] text-sf-brown/50">WS</div>
                      <div className="font-bold text-sf-brown">{rollGap.ws}mm</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-sf-brown/50">DS</div>
                      <div className="font-bold text-sf-brown">{rollGap.ds}mm</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-sf-brown/50">H</div>
                      <div className="font-bold text-sf-brown">{rollGap.h}mm</div>
                    </div>
                  </div>
                </div>
              )}
              {hmdLoaded !== undefined && (
                <div className="rounded-xl bg-sf-cream/50 border border-sf-orange/15 p-3">
                  <div className="text-[10px] font-bold text-sf-brown/60 mb-2">HMD 상태</div>
                  <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${hmdLoaded === true || hmdLoaded === 'ok' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    <span className="text-sm font-bold text-sf-brown">
                      {hmdLoaded === true || hmdLoaded === 'ok' ? '정상 (Loaded)' : '대기'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </motion.div>
    </div>
  );
};

// ─── 메인 컴포넌트 ───

export default function DashboardPanel({ auth, apiCall }) {
  const [dashboard, setDashboard] = useState(null);
  const [insights, setInsights] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);

  // 설비 선택
  const [selectedEquipment, setSelectedEquipment] = useState('FM-LINE1');
  const [equipmentList, setEquipmentList] = useState([]);

  // FMCS 스탠드 상태
  const [standData, setStandData] = useState(null);
  const [standLoading, setStandLoading] = useState(false);
  const [operationMode, setOperationMode] = useState('ai_auto');
  const [modeChanging, setModeChanging] = useState(false);
  const [chartStand, setChartStand] = useState('s1');
  const [chartData, setChartData] = useState([]);

  // 스탠드 히스토리 (스파크라인용 - 최근 10개 값)
  const [standHistory, setStandHistory] = useState({});

  // 스탠드 flash 효과 (값 변경 시)
  const [standFlash, setStandFlash] = useState({});
  const prevStandRef = useRef({});
  const flashTimeoutRef = useRef(null);

  // 스탠드 상세 모달
  const [selectedStand, setSelectedStand] = useState(null);
  const [selectedStandName, setSelectedStandName] = useState('');

  // M44: loadData를 useCallback으로 안정화
  const loadData = useCallback(async () => {
    setLoading(true);

    const [summaryRes, insightsRes, alertsRes] = await Promise.all([
      apiCall({
        endpoint: '/api/dashboard/summary',
        auth,
        timeoutMs: 30000,
      }),
      apiCall({
        endpoint: '/api/dashboard/insights',
        auth,
        timeoutMs: 10000,
      }),
      apiCall({
        endpoint: '/api/dashboard/alerts?limit=5',
        auth,
        timeoutMs: 10000,
      }),
    ]);

    setLoading(false);

    if (summaryRes?.status === 'success') {
      setDashboard(summaryRes);
    } else {
      setDashboard(null);
      toast.error('대시보드 데이터를 불러올 수 없습니다');
    }

    if (insightsRes?.status === 'success' && insightsRes.insights) {
      setInsights(insightsRes.insights);
    }

    if (alertsRes?.status === 'success' && alertsRes.alerts) {
      setAlerts(alertsRes.alerts);
    }
  }, [auth, apiCall]);

  // 설비 목록 로드
  useEffect(() => {
    apiCall({ endpoint: '/api/stands/equipment-list', auth }).then(res => {
      if (res?.equipment) setEquipmentList(res.equipment);
    });
  }, [apiCall, auth]);

  // FMCS 스탠드 상태 로드 (3초 폴링)
  const loadStandData = useCallback(async () => {
    setStandLoading(true);
    try {
      const res = await apiCall({ endpoint: `/api/stands/status?equipment=${selectedEquipment}`, auth, timeoutMs: 10000 });
      if (res?.stands) {
        // 스파크라인용 히스토리 누적
        setStandHistory(prev => {
          const next = { ...prev };
          res.stands.forEach(s => {
            const key = s.name || s.id;
            const arr = [...(next[key] || []), { current: s.current, speed: s.speed, load: s.load }];
            next[key] = arr.slice(-10); // 최근 10개
          });
          return next;
        });

        // flash 효과: 값 변경 감지
        const prevStands = prevStandRef.current;
        const flashes = {};
        res.stands.forEach(s => {
          const key = s.name || s.id;
          const prev = prevStands[key];
          if (prev && (prev.current !== s.current || prev.speed !== s.speed)) {
            flashes[key] = true;
          }
          prevStands[key] = { current: s.current, speed: s.speed };
        });
        prevStandRef.current = prevStands;
        if (Object.keys(flashes).length > 0) {
          setStandFlash(flashes);
          if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
          flashTimeoutRef.current = setTimeout(() => setStandFlash({}), 600);
        }

        setStandData(res);
        setOperationMode(res.operation_mode || 'ai_auto');
      }
    } catch (e) {
      console.error('스탠드 상태 로드 실패:', e);
    } finally {
      setStandLoading(false);
    }
  }, [auth, apiCall, selectedEquipment]);

  // Load vs Speed 차트 데이터 로드
  const loadChartData = useCallback(async () => {
    try {
      const res = await apiCall({ endpoint: `/api/stands/load-speed-chart?equipment=${selectedEquipment}`, auth, timeoutMs: 10000 });
      if (res?.data) setChartData(res.data);
    } catch (e) {
      console.error('차트 데이터 로드 실패:', e);
    }
  }, [auth, apiCall, selectedEquipment]);

  // 운전모드 변경
  const toggleOperationMode = useCallback(async () => {
    const newMode = operationMode === 'ai_auto' ? 'manual' : 'ai_auto';
    setModeChanging(true);
    try {
      const res = await apiCall({
        endpoint: '/api/stands/operation-mode',
        auth,
        method: 'POST',
        data: { mode: newMode },
      });
      if (res?.status === 'success') {
        setOperationMode(res.current_mode);
        toast.success(`운전모드 변경: ${res.current_mode === 'ai_auto' ? 'AI Auto-Pilot' : 'Manual Override'}`);
      } else {
        toast.error('운전모드 변경 실패');
      }
    } catch (e) {
      toast.error('운전모드 변경 실패');
    } finally {
      setModeChanging(false);
    }
  }, [operationMode, auth, apiCall]);

  // flash timeout cleanup on unmount
  useEffect(() => {
    return () => { if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current); };
  }, []);

  useEffect(() => {
    loadData();
    loadStandData();
    loadChartData();
  }, [loadData, loadStandData, loadChartData]);

  // 대시보드 자동 폴링 (60초, 탭 비활성 시 완전 중단 + 에러 백오프)
  usePolling(loadData, 60000);

  // FMCS 스탠드 3초 폴링 (탭 비활성 시 완전 중단)
  usePolling(loadStandData, 3000);

  // 차트 5초 폴링 (탭 비활성 시 완전 중단)
  usePolling(loadChartData, 5000);

  // 스탠드 카드 클릭 → 상세 모달
  const handleStandClick = useCallback((stand) => {
    // API expects integer stand_id (1~9), extract from name like "S1" or use id
    const standId = stand.id || stand.name?.replace(/\D/g, '') || stand.name;
    setSelectedStand(standId);
    setSelectedStandName(stand.name);
  }, []);

  const closeStandDetail = useCallback(() => {
    setSelectedStand(null);
    setSelectedStandName('');
  }, []);

  // 고위험 알림 필터
  const highSeverityAlerts = useMemo(() => {
    return alerts.filter(a => a.severity === 'high' || a.color === 'red');
  }, [alerts]);

  // FMCS 스탠드 알람 (high severity)
  const standAlarms = useMemo(() => {
    if (!standData?.alarms) return [];
    return standData.alarms.filter(a => a.severity === 'high');
  }, [standData]);

  // 선택된 스탠드 차트 데이터 매핑
  const selectedChartData = useMemo(() => {
    if (!chartData.length) return [];
    // 매 10번째 포인트만 사용 (성능)
    return chartData.filter((_, i) => i % 10 === 0).map(d => ({
      time: d.time?.slice(0, 8) || '',
      load: d[`${chartStand}_load`] ?? 0,
      speed: d[`${chartStand}_speed`] ?? 0,
    }));
  }, [chartData, chartStand]);

  return (
    <div>
      <SectionHeader
        title="스마트팩토리 AI 대시보드"
        subtitle="제조 현황 요약"
        right={
          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={loading}
              aria-label="데이터 새로고침"
              className="rounded-full border-2 border-sf-orange/20 bg-white/80 p-1.5 hover:bg-sf-beige transition disabled:opacity-50"
            >
              <RefreshCw size={14} className={`text-sf-brown ${loading ? 'animate-spin' : ''}`} />
            </button>
            {!loading && <LiveIndicator />}
          </div>
        }
      />

      {loading && !dashboard ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}

      {/* FMCS 스탠드 알람 배너 */}
      {standAlarms.length > 0 && (
        <FadeInSection delay={0.02} className="mb-4">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="rounded-2xl border-2 border-red-400 bg-red-50 p-4 shadow-md"
          >
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={18} className="text-red-600 animate-pulse" />
              <span className="text-sm font-black text-red-800">스탠드 긴급 알람</span>
              <span className="ml-auto px-2 py-0.5 rounded-full bg-red-600 text-white text-[10px] font-bold">
                {standAlarms.length}
              </span>
            </div>
            <div className="space-y-1.5">
              {standAlarms.map((alarm, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm text-red-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
                  <span className="font-semibold">
                    {alarm.stand}: {alarm.type} — 값: {alarm.value?.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </FadeInSection>
      )}

      {dashboard ? (
        <>
          {/* 1. 상단 KPI 카드 8개 (기존 6 + Line Speed, AI Confidence) */}
          <FadeInSection className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-8 gap-3 mb-6">
            {/* OEE 게이지 카드 */}
            <OeeGauge value={dashboard?.oee_gauge ?? 0} />

            <KpiCard
              title="Line Speed"
              value={<AnimatedValue value={standData?.line_speed ?? 0} decimals={1} suffix=" m/s" className="tabular-nums" />}
              subtitle="라인 속도"
              icon={<Activity size={18} className="text-sf-brown" />}
              tone="blue"
            />
            <KpiCard
              title="AI Confidence"
              value={<AnimatedValue value={(standData?.ai_confidence ?? 0) * 100} decimals={1} suffix="%" className="tabular-nums" />}
              subtitle="AI 신뢰도"
              icon={<Brain size={18} className="text-sf-brown" />}
              tone={(standData?.ai_confidence ?? 0) > 0.9 ? 'green' : 'orange'}
            />
            <KpiCard
              title="MTBF"
              value={<AnimatedValue value={dashboard?.mtbf ?? 0} decimals={1} suffix="h" className="tabular-nums" />}
              subtitle="평균 고장간격"
              icon={<Clock size={18} className="text-sf-brown" />}
              tone="blue"
            />
            <KpiCard
              title="MTTR"
              value={<AnimatedValue value={dashboard?.mttr ?? 0} decimals={1} suffix="h" className="tabular-nums" />}
              subtitle="평균 수리시간"
              icon={<Wrench size={18} className="text-sf-brown" />}
              tone="orange"
            />
            <KpiCard
              title="불량률"
              value={<AnimatedValue value={dashboard?.defect_rate ?? 0} decimals={2} suffix="%" className="tabular-nums" />}
              subtitle="금일 기준"
              icon={<AlertTriangle size={18} className="text-sf-brown" />}
              tone={dashboard?.defect_rate > 5 ? 'pink' : 'green'}
            />
            <KpiCard
              title="일 생산량"
              value={`${(dashboard?.production_rate ?? 0).toLocaleString()}본`}
              subtitle="금일 압연 실적"
              icon={<Factory size={18} className="text-sf-brown" />}
              tone="yellow"
            />
            <KpiCard
              title="라인 전력"
              value={<AnimatedValue value={dashboard?.energy_consumption ?? 0} decimals={1} suffix="kWh" className="tabular-nums" />}
              subtitle="금일 소비량"
              icon={<Zap size={18} className="text-sf-brown" />}
              tone="cream"
            />
          </FadeInSection>

          {/* 2. FMCS 스탠드 실시간 상태 그리드 */}
          {standData?.stands && (
            <FadeInSection delay={0.05} className="mb-6">
              <div className="flex items-center flex-wrap gap-2 mb-3">
                <Settings size={18} className="text-sf-orange" />
                <span className="text-sm font-black text-sf-brown">스탠드 실시간 현황</span>
                <div className="flex gap-2">
                  {equipmentList.map(eq => (
                    <button key={eq.id}
                      onClick={() => setSelectedEquipment(eq.id)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                        selectedEquipment === eq.id
                          ? 'bg-sf-orange text-white'
                          : 'bg-sf-cream text-sf-brown hover:bg-sf-orange/20'
                      }`}>
                      {eq.name}
                    </button>
                  ))}
                </div>
                <span className="ml-2 text-[10px] text-sf-brown/50 bg-sf-cream px-2 py-0.5 rounded-full">
                  {standData.current_production} | FDT {standData.fdt}°C
                </span>
                {standLoading && (
                  <div className="ml-auto w-4 h-4 border-2 border-sf-orange/30 border-t-sf-orange rounded-full animate-spin" />
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {standData.stands.map((s, idx) => {
                  const standKey = s.name || s.id;
                  const isFlashing = standFlash[standKey];
                  const history = standHistory[standKey] || [];
                  // 전류 미니바: 0~100% (base=2000A)
                  const currentPercent = Math.min(100, Math.max(0, (s.current / 2000) * 100));

                  return (
                    <motion.div
                      key={s.name}
                      initial={{ opacity: 0, y: 15 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.04, duration: 0.3 }}
                      onClick={() => handleStandClick(s)}
                      className={`group relative rounded-2xl border-2 bg-white/80 p-4 shadow-sm backdrop-blur transition-all duration-300 hover:shadow-lg hover:-translate-y-1 cursor-pointer ${
                        s.status === 'alarm' ? 'border-red-300 bg-red-50/50' :
                        s.status === 'warning' ? 'border-yellow-300 bg-yellow-50/30' :
                        isFlashing ? 'border-blue-400 bg-blue-50/30' :
                        'border-sf-orange/15'
                      }`}
                      style={{
                        borderColor: isFlashing ? '#60a5fa' : undefined,
                        transition: 'border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease',
                      }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-base font-black text-sf-brown">{s.name}</span>
                        <StandStatusBadge status={s.status} />
                      </div>
                      {/* 전류 수준 미니바 */}
                      <div className="mb-3">
                        <div className="flex justify-between items-center text-[9px] mb-0.5">
                          <span className="text-sf-brown/50">전류 수준</span>
                          <span className="font-bold text-sf-brown">{currentPercent.toFixed(0)}%</span>
                        </div>
                        <MiniProgressBar
                          value={currentPercent}
                          color={currentPercent > 80 ? '#ef4444' : currentPercent > 60 ? '#f59e0b' : '#1B6FF0'}
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="rounded-lg bg-sf-cream/50 p-1.5">
                          <div className="text-[9px] text-sf-brown/50">전류</div>
                          <AnimatedValue value={s.current} decimals={0} suffix="A" className="text-xs font-bold text-sf-brown" />
                        </div>
                        <div className="rounded-lg bg-sf-cream/50 p-1.5">
                          <div className="text-[9px] text-sf-brown/50">속도</div>
                          <AnimatedValue value={s.speed} decimals={1} suffix="m/s" className="text-xs font-bold text-sf-brown" />
                        </div>
                        <div className="rounded-lg bg-sf-cream/50 p-1.5">
                          <div className="text-[9px] text-sf-brown/50">AI보상</div>
                          <motion.div
                            key={s.ai_comp}
                            initial={{ scale: 1.2 }}
                            animate={{ scale: 1 }}
                            className={`text-xs font-bold ${s.ai_comp >= 0 ? 'text-emerald-600' : 'text-red-600'}`}
                          >
                            {s.ai_comp > 0 ? '+' : ''}{s.ai_comp}
                          </motion.div>
                        </div>
                        <div className="rounded-lg bg-sf-cream/50 p-1.5">
                          <div className="text-[9px] text-sf-brown/50">하중</div>
                          <AnimatedValue value={s.load} decimals={0} suffix="kN" className="text-xs font-bold text-sf-brown" />
                        </div>
                        <div className="rounded-lg bg-sf-cream/50 p-1.5">
                          <div className="text-[9px] text-sf-brown/50">온도</div>
                          <AnimatedValue value={s.temperature} decimals={0} suffix="°C" className="text-xs font-bold text-sf-brown" />
                        </div>
                        <div className="rounded-lg bg-sf-cream/50 p-1.5">
                          <div className="text-[9px] text-sf-brown/50">롤갭H</div>
                          <div className="text-xs font-bold text-sf-brown">{s.roll_gap?.h}mm</div>
                        </div>
                      </div>
                      {/* 스파크라인 */}
                      {history.length >= 2 && (
                        <div className="mt-2 flex items-center justify-between">
                          <MiniSparkline data={history} dataKey="current" color="#1B6FF0" />
                          <MiniSparkline data={history} dataKey="speed" color="#10b981" />
                          <MiniSparkline data={history} dataKey="load" color="#F97316" />
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </FadeInSection>
          )}

          {/* 2-1. Load vs Speed 복합 차트 */}
          <FadeInSection delay={0.08} className="mb-6">
            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur transition-all duration-300 hover:shadow-lg hover:-translate-y-1">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 size={18} className="text-sf-orange" />
                <span className="text-sm font-black text-sf-brown">Load vs Speed</span>
                <div className="ml-auto relative">
                  <select
                    value={chartStand}
                    onChange={(e) => setChartStand(e.target.value)}
                    className="appearance-none rounded-lg border border-sf-orange/30 bg-white px-3 py-1.5 pr-8 text-xs font-bold text-sf-brown cursor-pointer focus:outline-none focus:ring-2 focus:ring-sf-orange/30"
                  >
                    {['s1','s2','s3','s4','s5','s6','s7','s8','s9'].map(s => (
                      <option key={s} value={s}>{s.toUpperCase()}</option>
                    ))}
                  </select>
                  <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-sf-brown/50 pointer-events-none" />
                </div>
              </div>
              {selectedChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={selectedChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
                    <XAxis
                      dataKey="time"
                      tick={{ fill: '#5C4A3D', fontSize: 10 }}
                      tickLine={{ stroke: '#FFD93D60' }}
                      interval={3}
                    />
                    <YAxis
                      yAxisId="left"
                      tick={{ fill: '#5C4A3D', fontSize: 10 }}
                      tickFormatter={(v) => `${v}kN`}
                      label={{ value: '하중(kN)', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#5C4A3D' } }}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tick={{ fill: '#5C4A3D', fontSize: 10 }}
                      tickFormatter={(v) => `${v}m/s`}
                      label={{ value: '속도(m/s)', angle: 90, position: 'insideRight', style: { fontSize: 10, fill: '#5C4A3D' } }}
                    />
                    <Tooltip content={<LoadSpeedTooltip />} />
                    <Legend />
                    <Bar yAxisId="left" dataKey="load" name={`${chartStand.toUpperCase()} 하중`} fill="#1B6FF0" fillOpacity={0.7} radius={[4, 4, 0, 0]} animationDuration={300} />
                    <Line yAxisId="right" dataKey="speed" name={`${chartStand.toUpperCase()} 속도`} stroke="#F97316" strokeWidth={2} dot={false} animationDuration={300} />
                    {/* 최신 포인트 pulse dot */}
                    {selectedChartData.length > 0 && (
                      <ReferenceDot
                        yAxisId="right"
                        x={selectedChartData[selectedChartData.length - 1].time}
                        y={selectedChartData[selectedChartData.length - 1].speed}
                        r={5}
                        fill="#F97316"
                        stroke="#fff"
                        strokeWidth={2}
                      >
                        <animate attributeName="r" values="4;7;4" dur="1.5s" repeatCount="indefinite" />
                      </ReferenceDot>
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-sm text-sf-brown/60">
                  차트 데이터 로딩 중...
                </div>
              )}
            </div>
          </FadeInSection>

          {/* 3. 알람 배너 (고위험 알림) */}
          {highSeverityAlerts.length > 0 && (
            <FadeInSection delay={0.05} className="mb-6">
              <div className="rounded-2xl border-2 border-red-300 bg-red-50 p-4 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={18} className="text-red-600" />
                  <span className="text-sm font-black text-red-800">긴급 알림</span>
                  <span className="ml-auto px-2 py-0.5 rounded-full bg-red-500 text-white text-[10px] font-bold">
                    {highSeverityAlerts.length}
                  </span>
                </div>
                <div className="space-y-1.5">
                  {highSeverityAlerts.map((alert, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm text-red-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
                      <span className="font-semibold">
                        설비 {alert.equipment_id || alert.user_id}: {alert.type} 감지 — 즉시 점검 필요
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </FadeInSection>
          )}

          {/* 3. AI 인사이트 + 실시간 알림 */}
          <FadeInSection delay={0.2} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* AI 인사이트 */}
            <div className="rounded-3xl border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-white p-5 shadow-sm transition-all duration-300 hover:shadow-lg hover:-translate-y-1">
              <div className="flex items-center gap-2 mb-4">
                <Brain size={18} className="text-purple-600" />
                <span className="text-sm font-black text-purple-900">AI 인사이트</span>
                <span className="ml-auto px-2 py-0.5 rounded-full bg-purple-500 text-white text-[10px] font-bold hover:scale-105 transition-transform">
                  LIVE
                </span>
              </div>
              <div className="space-y-3">
                {insights.length > 0 ? insights.map((insight, idx) => {
                  const iconConfig = {
                    positive: { bg: 'bg-green-100', icon: <ArrowUpRight size={14} className="text-green-600" /> },
                    warning: { bg: 'bg-yellow-100', icon: <Target size={14} className="text-yellow-600" /> },
                    neutral: { bg: 'bg-blue-100', icon: <Zap size={14} className="text-blue-600" /> },
                  };
                  const config = iconConfig[insight.type] || iconConfig.neutral;

                  return (
                    <div key={idx} className="flex items-start gap-3 p-3 rounded-2xl bg-white/80 border border-purple-100">
                      <div className={`w-8 h-8 rounded-full ${config.bg} flex items-center justify-center flex-shrink-0`}>
                        {config.icon}
                      </div>
                      <div>
                        <div className="text-sm font-bold text-sf-brown">{insight.title}</div>
                        <div className="text-xs text-sf-brown/70">{insight.description}</div>
                      </div>
                    </div>
                  );
                }) : (
                  <div className="flex items-center justify-center p-4 text-sm text-sf-brown/50">
                    인사이트 로딩 중...
                  </div>
                )}
              </div>
            </div>

            {/* 실시간 알림 */}
            <div className="rounded-3xl border-2 border-red-200 bg-gradient-to-br from-red-50 to-white p-5 shadow-sm transition-all duration-300 hover:shadow-lg hover:-translate-y-1">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle size={18} className="text-red-600" />
                <span className="text-sm font-black text-red-900">실시간 알림</span>
                <span className="ml-auto px-2 py-0.5 rounded-full bg-red-500 text-white text-[10px] font-bold hover:scale-105 transition-transform">
                  {alerts.length || dashboard?.equipment_stats?.anomaly_count || 0}
                </span>
              </div>
              <div className="space-y-3">
                {alerts.length > 0 ? alerts.map((alert, idx) => {
                  const colorMap = {
                    red: { dot: 'bg-red-500', border: 'border-red-100', animate: idx === 0 },
                    orange: { dot: 'bg-orange-500', border: 'border-orange-100', animate: false },
                    yellow: { dot: 'bg-yellow-500', border: 'border-yellow-100', animate: false },
                  };
                  const colors = colorMap[alert.color] || colorMap.yellow;

                  return (
                    <div key={idx} className={`flex items-center gap-3 p-3 rounded-2xl bg-white/80 border ${colors.border}`}>
                      <div className={`w-2 h-2 rounded-full ${colors.dot} ${colors.animate ? 'animate-pulse' : ''}`} />
                      <div className="flex-1">
                        <div className="text-sm font-bold text-sf-brown">{alert.type}</div>
                        <div className="text-xs text-sf-brown/70">{alert.equipment_id || alert.user_id} - {alert.detail}</div>
                      </div>
                      <span className="text-[10px] text-sf-brown/50">{alert.time_ago}</span>
                    </div>
                  );
                }) : (
                  <div className="flex items-center justify-center p-4 text-sm text-sf-brown/50">
                    알림이 없습니다
                  </div>
                )}
              </div>
            </div>
          </FadeInSection>
        </>
      ) : (
        !loading && <EmptyState title="데이터가 없습니다" desc="백엔드 API 연결을 확인하세요." />
      )}

      {/* 스탠드 상세 모달 */}
      <AnimatePresence>
        {selectedStand && (
          <StandDetailModal
            standId={selectedStand}
            standName={selectedStandName}
            apiCall={apiCall}
            auth={auth}
            onClose={closeStandDetail}
            equipment={selectedEquipment}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
