// components/panels/StandControlPanel.js
// FMCS 스탠드 제어 패널 - 본 진행현황, AI 자동제어 적용률, Roll Gap, HMD 상태
// 실시간 제어 시각화: 빌렛 이동 애니메이션, 스텝 인디케이터, 스탠드 상세 패널

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { usePageVisibility, usePolling } from '@/components/panels/hooks/usePageVisibility';
import { motion, AnimatePresence } from 'framer-motion';
import SectionHeader from '@/components/SectionHeader';
import {
  RefreshCw, Settings, Activity, ToggleLeft, ToggleRight, Gauge,
  Check, TrendingUp, TrendingDown, Minus, Zap,
} from 'lucide-react';
import RealtimeLineCanvas, { RealtimeMultiLineCanvas } from '@/components/RealtimeLineCanvas';

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

// 미니 프로그레스 바 (부드러운 전환)
const ProgressBar = memo(({ value = 0, color = '#10b981', height = 'h-3' }) => (
  <div className={`w-full ${height} rounded-full bg-gray-200 overflow-hidden`}>
    <motion.div
      className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600"
      style={color !== '#10b981' ? { background: color } : undefined}
      initial={{ width: 0 }}
      animate={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
    />
  </div>
));

// 카운팅 애니메이션 숫자
const AnimatedNumber = memo(({ value, suffix = '', className = '' }) => {
  const [display, setDisplay] = useState(0);
  const prevRef = useRef(0);
  const rafRef = useRef(null);

  useEffect(() => {
    const from = prevRef.current;
    const to = typeof value === 'number' ? value : 0;
    if (from === to) return;

    const duration = 600;
    const start = performance.now();

    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round((from + (to - from) * eased) * 100) / 100);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
      else prevRef.current = to;
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [value]);

  return <span className={className}>{display}{suffix}</span>;
});

// 스텝 인디케이터 컴포넌트 (S1~S9)
const StepIndicator = memo(({ standsPassed = 0 }) => {
  const stands = Array.from({ length: 9 }, (_, i) => i + 1);

  return (
    <div className="flex items-center w-full py-3 px-1">
      {stands.map((s, idx) => {
        const isCompleted = s <= standsPassed;
        const isCurrent = s === standsPassed + 1;
        const isPending = s > standsPassed + 1;

        return (
          <div key={s} className="flex items-center flex-1">
            {/* 연결선 (첫 번째 제외) */}
            {idx > 0 && (
              <div className="flex-1 h-0.5 relative overflow-hidden">
                <div className={`h-full ${isCompleted ? 'bg-emerald-400' : 'bg-gray-200'}`} />
                {isCurrent && (
                  <motion.div
                    className="absolute top-0 h-full w-3 bg-gradient-to-r from-transparent via-orange-400 to-transparent"
                    animate={{ left: ['-12px', '100%'] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                  />
                )}
              </div>
            )}

            {/* 원형 인디케이터 */}
            <div className="relative flex-shrink-0">
              {isCurrent ? (
                <motion.div
                  className="w-7 h-7 rounded-full bg-orange-500 flex items-center justify-center shadow-md"
                  animate={{ scale: [1, 1.15, 1], boxShadow: ['0 0 0 0 rgba(249,115,22,0.4)', '0 0 0 8px rgba(249,115,22,0)', '0 0 0 0 rgba(249,115,22,0.4)'] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  <span className="text-[9px] font-black text-white">S{s}</span>
                </motion.div>
              ) : (
                <div className={`w-7 h-7 rounded-full flex items-center justify-center ${
                  isCompleted
                    ? 'bg-emerald-500 shadow-sm'
                    : 'bg-gray-200'
                }`}>
                  {isCompleted ? (
                    <Check size={12} className="text-white" strokeWidth={3} />
                  ) : (
                    <span className="text-[9px] font-bold text-gray-400">S{s}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});

export default function StandControlPanel({ auth, apiCall }) {
  // 설비 선택
  const [selectedEquipment, setSelectedEquipment] = useState('FM-LINE1');
  const [equipmentList, setEquipmentList] = useState([]);

  const [controlData, setControlData] = useState(null);
  const [standStatus, setStandStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cascadeMode, setCascadeMode] = useState(true);
  const [operationMode, setOperationMode] = useState('ai_auto');
  const [modeChanging, setModeChanging] = useState(false);
  const [selectedStand, setSelectedStand] = useState(null);
  const [standDetail, setStandDetail] = useState(null);
  const [standDetailLoading, setStandDetailLoading] = useState(false);
  // 스탠드별 전류 시계열 (0.25초 간격 클라이언트 시뮬레이션)
  const [currentHistory, setCurrentHistory] = useState(() => {
    const init = {};
    for (let i = 1; i <= 9; i++) init[i] = [];
    return init;
  });
  const standBaseRef = useRef({}); // API에서 받은 최신 전류 기준값

  // 설비 목록 로드
  useEffect(() => {
    apiCall({ endpoint: '/api/stands/equipment-list', auth }).then(res => {
      if (res?.equipment) setEquipmentList(res.equipment);
    });
  }, [apiCall, auth]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [controlRes, statusRes] = await Promise.all([
        apiCall({ endpoint: `/api/stands/control?equipment=${selectedEquipment}`, auth, timeoutMs: 10000 }),
        apiCall({ endpoint: `/api/stands/status?equipment=${selectedEquipment}`, auth, timeoutMs: 10000 }),
      ]);
      if (controlRes?.pieces) {
        setControlData(controlRes);
        setCascadeMode(controlRes.cascade_mode ?? true);
      }
      if (statusRes?.stands) {
        setStandStatus(statusRes.stands);
        if (statusRes.operation_mode) setOperationMode(statusRes.operation_mode);
        const bases = {};
        statusRes.stands.forEach(s => { bases[s.id] = s.current; });
        standBaseRef.current = bases;
      }
    } catch (e) {
      console.error('스탠드 제어 데이터 로드 실패:', e);
    } finally {
      setLoading(false);
    }
  }, [auth, apiCall, selectedEquipment]);

  useEffect(() => {
    loadData();
    // 라인 변경 시 차트 히스토리 초기화 (이전 라인 데이터 섞임 방지)
    setCurrentHistory(() => {
      const init = {};
      for (let i = 1; i <= 9; i++) init[i] = [];
      return init;
    });
  }, [loadData]);

  // 250ms 간격 스탠드 데이터 생성 (탭 비활성 시 완전 중단)
  const isVisible = usePageVisibility();
  useEffect(() => {
    if (!isVisible) return;
    const interval = setInterval(() => {
      const bases = standBaseRef.current;
      if (!bases || Object.keys(bases).length === 0) return;
      const now = Date.now();
      setCurrentHistory(prev => {
        const next = {};
        for (let i = 1; i <= 9; i++) {
          const base = bases[i] || 400;
          const t = now / 1000;
          const noise = (Math.random() - 0.5) * base * 0.02;
          const wave = Math.sin(t * (0.8 + i * 0.1) + i) * base * 0.03;
          const val = Math.round((base + wave + noise) * 10) / 10;
          const arr = [...(prev[i] || []), { t: now, v: val }];
          next[i] = arr.slice(-80); // 최근 20초 (80 × 250ms)
        }
        return next;
      });
    }, 250);
    return () => clearInterval(interval);
  }, [isVisible]);

  // 2초 폴링 (탭 비활성 시 완전 중단 + 에러 백오프)
  usePolling(loadData, 2000);

  // 운전모드 변경
  const toggleOperationMode = useCallback(async () => {
    const newMode = operationMode === 'ai_auto' ? 'manual' : 'ai_auto';
    setModeChanging(true);
    try {
      const res = await apiCall({ endpoint: '/api/stands/operation-mode', auth, method: 'POST', data: { mode: newMode } });
      if (res?.status === 'success') {
        setOperationMode(res.current_mode);
        toast.success(`운전모드: ${res.current_mode === 'ai_auto' ? 'AI Auto-Pilot' : 'Manual Override'}`);
      } else {
        toast.error('운전모드 변경 실패');
      }
    } catch { toast.error('운전모드 변경 실패'); }
    finally { setModeChanging(false); }
  }, [operationMode, auth, apiCall]);

  // 스탠드 상세 데이터 로드
  const loadStandDetail = useCallback(async (standId) => {
    setStandDetailLoading(true);
    try {
      const res = await apiCall({ endpoint: `/api/stands/${standId}/detail?equipment=${selectedEquipment}`, auth, timeoutMs: 10000 });
      if (res) setStandDetail(res);
    } catch (e) {
      console.error('스탠드 상세 데이터 로드 실패:', e);
    } finally {
      setStandDetailLoading(false);
    }
  }, [auth, apiCall, selectedEquipment]);

  // 선택된 스탠드 상세 2초 폴링 (탭 비활성 시 완전 중단)
  const loadSelectedStandDetail = useCallback(() => {
    if (selectedStand) loadStandDetail(selectedStand);
  }, [selectedStand, loadStandDetail]);
  usePolling(loadSelectedStandDetail, 2000, { enabled: !!selectedStand, immediate: true });

  // 스탠드 상세 닫기 핸들러
  const closeStandDetail = useCallback(() => {
    setSelectedStand(null);
    setStandDetail(null);
  }, []);

  // 스탠드 클릭 핸들러
  const handleStandClick = useCallback((standName) => {
    const standId = parseInt(standName.replace('S', ''));
    if (selectedStand === standId) {
      setSelectedStand(null);
      setStandDetail(null);
    } else {
      setSelectedStand(standId);
      setStandDetail(null);
    }
  }, [selectedStand]);


  // 빌렛 위치 계산
  const billetPosition = useMemo(() => {
    if (!controlData?.hmd_status) return 0;
    const loaded = controlData.hmd_status.filter(h => h.loaded);
    return loaded.length > 0 ? loaded[loaded.length - 1].stand : 'S0';
  }, [controlData]);

  const billetStandIndex = useMemo(() => {
    if (!billetPosition || billetPosition === 'S0') return 0;
    const match = typeof billetPosition === 'string' ? billetPosition.match(/\d+/) : null;
    return match ? parseInt(match[0]) : 0;
  }, [billetPosition]);

  // 진행중 본
  const currentPiece = useMemo(() => controlData?.pieces?.find(p => p.status === 'in_progress'), [controlData]);
  const completedPieces = useMemo(() => controlData?.pieces?.filter(p => p.status === 'completed') || [], [controlData]);

  return (
    <div>
      <SectionHeader
        title="스탠드 제어 현황"
        subtitle="FMCS 스탠드 제어 및 모니터링"
        right={
          <div className="flex items-center gap-2">
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
            <button
              onClick={loadData}
              disabled={loading}
              aria-label="데이터 새로고침"
              className="rounded-full border-2 border-sf-orange/20 bg-white/80 p-1.5 hover:bg-sf-beige transition disabled:opacity-50"
            >
              <RefreshCw size={14} className={`text-sf-brown ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        }
      />

      {/* 운전 모드 토글 */}
      <FadeInSection className="mb-4">
        <div className="flex items-center justify-between rounded-2xl border-2 border-sf-orange/20 bg-white/80 px-5 py-3 shadow-sm backdrop-blur">
          <div className="flex items-center gap-3">
            <Gauge size={20} className="text-sf-orange" />
            <span className="text-sm font-black text-sf-brown">운전 모드</span>
            {operationMode === 'manual' && (
              <span className="text-[10px] font-bold text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full">AI 예측 비활성</span>
            )}
          </div>
          <button
            onClick={toggleOperationMode}
            disabled={modeChanging}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-sm transition-all duration-300 ${
              operationMode === 'ai_auto'
                ? 'bg-emerald-500 text-white hover:bg-emerald-600'
                : 'bg-orange-500 text-white hover:bg-orange-600'
            } disabled:opacity-50`}
          >
            {operationMode === 'ai_auto' ? (
              <><ToggleRight size={18} /> AI Auto-Pilot</>
            ) : (
              <><ToggleLeft size={18} /> Manual Override</>
            )}
          </button>
        </div>
      </FadeInSection>

      {controlData ? (
        <>
          {/* 1. 본(Piece) 진행 현황 + AI 자동제어 적용률 */}
          <FadeInSection className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* 본 진행 현황 */}
            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
              <div className="flex items-center gap-2 mb-4">
                <Activity size={18} className="text-sf-orange" />
                <span className="text-sm font-black text-sf-brown">본(Piece) 진행 현황</span>
                <span className="ml-auto text-[10px] text-sf-brown/50 bg-sf-cream px-2 py-0.5 rounded-full">
                  {controlData.product_spec}
                </span>
              </div>

              {/* 현재 진행중 본 */}
              {currentPiece && (
                <div className="mb-4 p-4 rounded-2xl bg-gradient-to-r from-emerald-50 to-white border border-emerald-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-sf-brown">
                      #{currentPiece.piece_no} {currentPiece.product_spec}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold">
                      진행중
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    <ProgressBar value={currentPiece.progress} color="#10b981" />
                    <span className="text-xs font-bold text-emerald-600 min-w-[40px] text-right">
                      {currentPiece.progress}%
                    </span>
                  </div>

                  {/* 스텝 인디케이터 */}
                  <StepIndicator standsPassed={currentPiece.stands_passed} />

                  <div className="text-[10px] text-sf-brown/60">
                    통과 스탠드: S1~S{currentPiece.stands_passed} ({currentPiece.stands_passed}/9)
                  </div>
                </div>
              )}

              {/* 최근 완료 본 */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-sf-brown/60 mb-1">최근 완료</div>
                {completedPieces.map((p) => (
                  <div key={p.piece_no} className="flex items-center justify-between p-2 rounded-xl bg-gray-50 border border-gray-100">
                    <span className="text-xs font-semibold text-sf-brown">#{p.piece_no}</span>
                    <span className="text-[10px] text-sf-brown/60">{p.product_spec}</span>
                    <span className="px-2 py-0.5 rounded-full bg-gray-200 text-gray-600 text-[10px] font-bold">완료</span>
                  </div>
                ))}
              </div>

              {/* 요약 */}
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-emerald-50 p-2">
                  <div className="text-[9px] text-emerald-600/70">자동</div>
                  <div className="text-sm font-black text-emerald-700">{controlData.ai_auto_count}</div>
                </div>
                <div className="rounded-xl bg-orange-50 p-2">
                  <div className="text-[9px] text-orange-600/70">수동</div>
                  <div className="text-sm font-black text-orange-700">{controlData.manual_count}</div>
                </div>
                <div className="rounded-xl bg-blue-50 p-2">
                  <div className="text-[9px] text-blue-600/70">전체</div>
                  <div className="text-sm font-black text-blue-700">{controlData.total_pieces}</div>
                </div>
              </div>
            </div>

            {/* AI 자동제어 적용률 게이지 - CSS transition 기반 */}
            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
              <div className="flex items-center gap-2 mb-4">
                <Gauge size={18} className="text-sf-orange" />
                <span className="text-sm font-black text-sf-brown">AI 자동 제어 적용률</span>
              </div>
              <div className="flex flex-col items-center">
                {(() => {
                  const rawRate = controlData.ai_auto_rate ?? 0;
                  const rate = Math.round(rawRate);
                  const r = 80;
                  const stroke = 20;
                  const cx = 120;
                  const cy = 100;
                  // 반원: 180° → 0° (왼→오)
                  const totalLen = Math.PI * r; // 반원 둘레
                  const filledLen = (rate / 100) * totalLen;
                  const gapLen = totalLen - filledLen;
                  // 색상: 90%이상 초록, 70%이상 노랑, 미만 빨강
                  const color = rate >= 90 ? '#10b981' : rate >= 70 ? '#f59e0b' : '#ef4444';
                  return (
                    <svg viewBox="0 0 240 130" width="100%" style={{ maxWidth: 320 }}>
                      {/* 배경 반원 */}
                      <path
                        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
                        fill="none"
                        stroke="#e5e7eb"
                        strokeWidth={stroke}
                        strokeLinecap="round"
                      />
                      {/* 채워지는 반원 - CSS transition */}
                      <path
                        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
                        fill="none"
                        stroke={color}
                        strokeWidth={stroke}
                        strokeLinecap="round"
                        strokeDasharray={`${filledLen} ${gapLen}`}
                        style={{ transition: 'stroke-dasharray 1.2s ease-out, stroke 0.5s ease' }}
                      />
                      {/* 중앙 텍스트 */}
                      <text x={cx} y={cy - 12} textAnchor="middle" className="text-3xl font-black" fill="#3d2e22" fontSize="32" fontWeight="900">
                        {rate}%
                      </text>
                    </svg>
                  );
                })()}
                <div className="text-xs text-sf-brown/60 -mt-2">
                  자동 {controlData.ai_auto_count}본 / 수동 {controlData.manual_count}본 / 전체 {controlData.total_pieces}본
                </div>
              </div>
            </div>
          </FadeInSection>

          {/* 2. 제품 규격별 Roll Gap 테이블 */}
          <FadeInSection delay={0.1} className="mb-6">
            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
              <div className="flex items-center gap-2 mb-4">
                <Settings size={18} className="text-sf-orange" />
                <span className="text-sm font-black text-sf-brown">Roll Gap 현황</span>
                <span className="ml-2 text-[10px] text-sf-brown/50 bg-sf-cream px-2 py-0.5 rounded-full">
                  {controlData.product_spec}
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b-2 border-sf-orange/20">
                      <th className="py-2 px-3 text-left text-xs font-black text-sf-brown/70">스탠드</th>
                      <th className="py-2 px-3 text-center text-xs font-black text-sf-brown/70">속도 (m/s)</th>
                      <th className="py-2 px-3 text-center text-xs font-black text-sf-brown/70">하중 (kN)</th>
                      <th className="py-2 px-3 text-center text-xs font-black text-sf-brown/70">WS</th>
                      <th className="py-2 px-3 text-center text-xs font-black text-sf-brown/70">DS</th>
                      <th className="py-2 px-3 text-center text-xs font-black text-sf-brown/70">H</th>
                    </tr>
                  </thead>
                  <tbody>
                    {controlData.roll_gaps?.map((rg, idx) => (
                      <motion.tr
                        key={rg.stand}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.03 }}
                        className={`border-b border-sf-orange/10 cursor-pointer transition-all duration-200 ${
                          selectedStand === idx + 1
                            ? 'bg-orange-50 border-l-4 border-l-orange-400'
                            : 'hover:bg-sf-cream/30'
                        }`}
                        onClick={() => handleStandClick(rg.stand)}
                      >
                        {(() => {
                          const ss = standStatus?.find(s => s.name === rg.stand);
                          const spd = ss?.speed;
                          const ld = ss?.load;
                          return (
                            <>
                              <td className="py-2 px-3 font-bold text-sf-brown">{rg.stand}</td>
                              <td className="py-2 px-3 text-center tabular-nums text-sf-brown/80">
                                {spd != null ? spd.toFixed(2) : '-'}
                              </td>
                              <td className="py-2 px-3 text-center tabular-nums text-sf-brown/80">
                                {ld != null ? ld.toFixed(0) : '-'}
                              </td>
                              <td className="py-2 px-3 text-center text-sf-brown/80">{rg.ws}</td>
                              <td className="py-2 px-3 text-center text-sf-brown/80">{rg.ds}</td>
                              <td className="py-2 px-3 text-center font-bold text-sf-brown">{rg.h}</td>
                            </>
                          );
                        })()}
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 스탠드별 실시간 전류 차트 (0.25초 갱신) */}
              <div className="mt-4 pt-4 border-t-2 border-sf-orange/10">
                <div className="flex items-center gap-2 mb-3">
                  <Zap size={16} className="text-orange-500" />
                  <span className="text-xs font-black text-sf-brown">스탠드별 전류 실시간 모니터링</span>
                  <span className="text-[9px] text-sf-brown/40 ml-1">250ms 갱신</span>
                  <span className="ml-auto flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[9px] text-green-600 font-bold">LIVE</span>
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(sid => {
                    const data = (currentHistory[sid] || []);
                    const latest = data.length > 0 ? data[data.length - 1].v : 0;
                    const ss = standStatus?.find(s => s.id === sid);
                    const status = ss?.status || 'normal';
                    const borderColor = status === 'alarm' ? 'border-red-300' : status === 'warning' ? 'border-orange-300' : 'border-sf-orange/15';
                    return (
                      <div key={sid} className={`rounded-xl border-2 ${borderColor} bg-white/60 p-2 cursor-pointer hover:shadow-md transition-all`}
                        onClick={() => handleStandClick(`S${sid}`)}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] font-black text-sf-brown">S{sid}</span>
                          <div className="flex items-center gap-1">
                            {operationMode === 'manual' && (
                              <span className="text-[8px] font-bold text-orange-500 bg-orange-50 px-1 rounded">M</span>
                            )}
                            <span className={`text-[10px] font-bold tabular-nums ${latest > 600 ? 'text-red-600' : latest > 450 ? 'text-orange-600' : 'text-emerald-600'}`}>
                              {latest.toFixed(1)}A
                            </span>
                          </div>
                        </div>
                        {data.length > 2 && (
                          <RealtimeLineCanvas
                            data={data}
                            color={latest > 600 ? '#dc2626' : latest > 450 ? '#ea580c' : '#059669'}
                            width={200}
                            height={50}
                            lineWidth={1.5}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 스탠드 상세 확장 패널 */}
              <AnimatePresence mode="wait">
                {selectedStand && (
                  <StandDetailPanel
                    key={selectedStand}
                    standId={selectedStand}
                    detail={standDetail}
                    loading={standDetailLoading}
                    currentPiece={currentPiece}
                    onClose={closeStandDetail}
                  />
                )}
              </AnimatePresence>
            </div>
          </FadeInSection>

          {/* 3. HMD 장입 상태 + 빌렛 이동 */}
          <FadeInSection delay={0.15} className="mb-6">
            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
              <div className="flex items-center gap-2 mb-4">
                <Activity size={18} className="text-sf-orange" />
                <span className="text-sm font-black text-sf-brown">HMD 장입 상태</span>
              </div>

              {/* HMD 카드 */}
              <div className="flex gap-2 overflow-x-auto pb-2">
                {controlData.hmd_status?.map((hmd, idx) => {
                  const standNum = parseInt(hmd.stand.replace('S', ''));
                  const isActive = hmd.loaded && standNum === billetStandIndex;
                  const isCompleted = hmd.loaded && standNum < billetStandIndex;

                  return (
                    <motion.div
                      key={hmd.stand}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.06, duration: 0.4 }}
                      className={`flex-shrink-0 w-20 rounded-2xl p-3 text-center border-2 transition-all duration-300 cursor-pointer ${
                        isActive
                          ? 'bg-orange-50 border-orange-400 shadow-md shadow-orange-200'
                          : isCompleted
                            ? 'bg-emerald-50/70 border-emerald-200'
                            : hmd.loaded
                              ? 'bg-emerald-50 border-emerald-300 shadow-sm'
                              : 'bg-gray-50 border-gray-200'
                      }`}
                      onClick={() => handleStandClick(hmd.stand)}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <div className="text-xs font-black text-sf-brown mb-1">{hmd.stand}</div>
                      <div className={`w-10 h-10 mx-auto rounded-full flex items-center justify-center ${
                        isActive ? 'bg-orange-500' : hmd.loaded ? 'bg-emerald-500' : 'bg-gray-300'
                      }`}>
                        {isActive ? (
                          <motion.div
                            className="w-4 h-4 bg-white rounded-sm"
                            animate={{ rotate: [0, 5, -5, 0], scale: [1, 1.1, 1] }}
                            transition={{ duration: 0.5, repeat: Infinity }}
                          />
                        ) : hmd.loaded ? (
                          isCompleted ? (
                            <Check size={14} className="text-white" strokeWidth={3} />
                          ) : (
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              className="w-4 h-4 bg-white rounded-sm"
                            />
                          )
                        ) : null}
                      </div>
                      <div className={`text-[10px] font-bold mt-1 ${
                        isActive ? 'text-orange-600' : hmd.loaded ? 'text-emerald-700' : 'text-gray-400'
                      }`}>
                        {isActive ? 'ACTIVE' : hmd.loaded ? 'LOADED' : 'EMPTY'}
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* 레일 트랙 + 빌렛 이동 애니메이션 */}
              <div className="mt-3 relative h-8 bg-gradient-to-r from-gray-100 via-gray-50 to-gray-100 rounded-full overflow-hidden border border-gray-200">
                {/* 레일 라인 */}
                <div className="absolute inset-y-0 left-[5%] right-[5%] flex items-center">
                  <div className="w-full h-1 bg-gray-300 rounded-full" />
                </div>

                {/* 스탠드 위치 마커 */}
                {Array.from({ length: 9 }, (_, i) => (
                  <div
                    key={i}
                    className="absolute top-1/2 -translate-y-1/2 w-1.5 h-4 bg-gray-300 rounded-full"
                    style={{ left: `${5 + i * (90 / 8)}%` }}
                  />
                ))}

                {/* 빌렛 아이콘 */}
                <motion.div
                  className="absolute top-1 h-6 w-14 bg-gradient-to-r from-orange-500 to-red-500 rounded-lg shadow-lg flex items-center justify-center"
                  animate={{ left: `${Math.max(2, 5 + (billetStandIndex - 1) * (90 / 8) - 3)}%` }}
                  transition={{ type: 'spring', damping: 15, stiffness: 100 }}
                >
                  <span className="text-[8px] font-black text-white">BILLET</span>
                </motion.div>

                {/* 라벨 */}
                <div className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-sf-brown/30 pointer-events-none">
                  S1 → S9
                </div>
              </div>
            </div>
          </FadeInSection>

          {/* 4. Cascade Mode 토글 */}
          <FadeInSection delay={0.2} className="mb-6">
            <div className="relative">
              <div className="flex items-center justify-between rounded-2xl border-2 border-sf-orange/20 bg-white/80 px-5 py-3 shadow-sm backdrop-blur">
                <div className="flex items-center gap-3">
                  <Settings size={18} className="text-sf-orange" />
                  <span className="text-sm font-black text-sf-brown">Cascade Mode</span>
                  <span className="text-[10px] text-sf-brown/50">스탠드 연동 제어</span>
                </div>
                <button
                  onClick={() => {
                    setCascadeMode(!cascadeMode);
                    toast.success(`Cascade Mode ${!cascadeMode ? 'ON' : 'OFF'}`);
                  }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-sm transition-all duration-300 ${
                    cascadeMode
                      ? 'bg-emerald-500 text-white hover:bg-emerald-600'
                      : 'bg-gray-400 text-white hover:bg-gray-500'
                  }`}
                >
                  {cascadeMode ? (
                    <><ToggleRight size={18} /> ON</>
                  ) : (
                    <><ToggleLeft size={18} /> OFF</>
                  )}
                </button>
              </div>

              {/* Cascade 연결선 시각화 */}
              <AnimatePresence>
                {cascadeMode && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-2 rounded-2xl border-2 border-emerald-200 bg-emerald-50/50 p-4 overflow-hidden"
                  >
                    <div className="flex items-center gap-1 overflow-x-auto">
                      {Array.from({ length: 9 }, (_, i) => (
                        <div key={i} className="flex items-center">
                          <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-white border-2 border-emerald-300 flex items-center justify-center shadow-sm">
                            <span className="text-[10px] font-black text-emerald-700">S{i + 1}</span>
                          </div>
                          {i < 8 && (
                            <div className="flex-shrink-0 w-6 h-0.5 relative overflow-hidden">
                              <div className="h-full bg-emerald-300" />
                              <motion.div
                                className="absolute top-0 h-full w-2 bg-emerald-500 rounded-full"
                                animate={{ left: ['-8px', '24px'] }}
                                transition={{ duration: 0.8, repeat: Infinity, ease: 'linear', delay: i * 0.1 }}
                              />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 text-[10px] text-emerald-600/70 text-center">
                      스탠드 간 연동 제어 활성 - 데이터 실시간 동기화 중
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </FadeInSection>
        </>
      ) : (
        loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-10 h-10 border-4 border-sf-orange/30 border-t-sf-orange rounded-full animate-spin" />
          </div>
        ) : (
          <div className="flex items-center justify-center py-20 text-sm text-sf-brown/60">
            스탠드 제어 데이터를 불러올 수 없습니다
          </div>
        )
      )}
    </div>
  );
}

// =============================================================
// 스탠드 상세 확장 패널
// =============================================================
function StandDetailPanel({ standId, detail, loading, currentPiece, onClose }) {
  // 0.25초 클라이언트 보간으로 실시간 느낌
  const [localSeries, setLocalSeries] = useState([]);
  const detailBaseRef = useRef(null);

  // API에서 받은 최신값을 기준으로 저장
  useEffect(() => {
    if (detail?.control_values) {
      detailBaseRef.current = { cv: detail.control_values, stand: detail.stand };
    }
  }, [detail]);

  // 250ms마다 데이터 생성 (탭 비활성 시 완전 중단)
  const detailVisible = usePageVisibility();
  useEffect(() => {
    if (!detailVisible) return;
    const interval = setInterval(() => {
      const base = detailBaseRef.current;
      if (!base) return;
      const t = Date.now() / 1000;
      const cvBase = base.cv;
      const sBase = base.stand;
      const wave = Math.sin(t * 1.2 + standId) * 0.005;
      const noise = (Math.random() - 0.5) * 0.008;
      const curWave = Math.sin(t * (0.8 + standId * 0.1)) * (sBase?.current || 400) * 0.03;
      const curNoise = (Math.random() - 0.5) * (sBase?.current || 400) * 0.02;

      setLocalSeries(prev => {
        const pt = {
          _t: Date.now(),
          time: new Date().toLocaleTimeString('ko-KR', { hour12: false }),
          setpoint: +((cvBase.setpoint || 0) + wave).toFixed(3),
          actual: +((cvBase.actual || 0) + wave + noise).toFixed(3),
          current: +((sBase?.current || 0) + curWave + curNoise).toFixed(1),
          speed: +((sBase?.speed || 0) + wave * 10 + noise * 5).toFixed(2),
        };
        return [...prev, pt].slice(-80);
      });
    }, 250);
    return () => clearInterval(interval);
  }, [standId, detailVisible]);

  // 차트 데이터: localSeries 사용
  const chartData = localSeries;

  // 실시간 제어값: localSeries 최신값 우선, 없으면 API 값
  const latestLocal = localSeries.length > 0 ? localSeries[localSeries.length - 1] : null;
  const cv = useMemo(() => latestLocal ? {
    setpoint: latestLocal.setpoint,
    actual: latestLocal.actual,
    delta: +(latestLocal.setpoint - latestLocal.actual).toFixed(4),
    ai_recommendation: detail?.control_values?.ai_recommendation,
    mode: detail?.control_values?.mode,
  } : (detail?.control_values || {}), [latestLocal, detail?.control_values]);
  const delta = cv.delta;

  const deltaColor = useCallback((val) => {
    if (val == null || val === 0) return 'text-gray-500';
    return val > 0 ? 'text-emerald-600' : 'text-red-500';
  }, []);

  const deltaIcon = useCallback((val) => {
    if (val == null || val === 0) return <Minus size={14} />;
    return val > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />;
  }, []);

  // 속도 차이 계산
  const speedDiff = (cv.setpoint != null && cv.actual != null)
    ? round4(cv.actual - cv.setpoint)
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="overflow-hidden"
    >
      <div className="mt-4 p-4 rounded-2xl bg-gradient-to-br from-orange-50/80 to-white border-2 border-orange-200">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-orange-500" />
            <span className="text-sm font-black text-sf-brown">S{standId} 상세 제어값</span>
            <span className="flex items-center gap-1 ml-2">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[9px] text-green-600 font-bold">250ms</span>
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-xs text-sf-brown/50 hover:text-sf-brown px-2 py-1 rounded-lg hover:bg-white transition"
          >
            닫기
          </button>
        </div>

        {loading && !detail ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-orange-300 border-t-orange-500 rounded-full animate-spin" />
          </div>
        ) : detail ? (
          <>
            {/* 제어값 카드 4개 */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              {/* 지시속도 */}
              <div className="rounded-xl bg-white p-3 border border-gray-100 shadow-sm">
                <div className="text-[10px] text-sf-brown/50 mb-1">지시속도 (Setpoint)</div>
                <div className="text-xl font-black text-sf-brown">
                  {cv.setpoint ?? '-'}
                </div>
                <div className="text-[10px] text-sf-brown/40">m/s</div>
              </div>

              {/* 실제속도 */}
              <div className="rounded-xl bg-white p-3 border border-gray-100 shadow-sm">
                <div className="text-[10px] text-sf-brown/50 mb-1">실제속도 (Actual)</div>
                <div className="text-xl font-black text-sf-brown">
                  {cv.actual ?? '-'}
                </div>
                <div className={`text-[10px] font-bold ${
                  speedDiff != null && Math.abs(speedDiff) > 0.1 ? 'text-red-500' : 'text-emerald-500'
                }`}>
                  {speedDiff != null ? `차이: ${speedDiff > 0 ? '+' : ''}${speedDiff}` : '-'} m/s
                </div>
              </div>

              {/* 변화량 */}
              <div className="rounded-xl bg-white p-3 border border-gray-100 shadow-sm">
                <div className="text-[10px] text-sf-brown/50 mb-1">변화량 (Delta)</div>
                <div className={`text-xl font-black flex items-center gap-1 ${deltaColor(delta)}`}>
                  {deltaIcon(delta)}
                  {delta != null ? Math.abs(delta) : '-'}
                </div>
                <div className="text-[10px] text-sf-brown/40">m/s</div>
              </div>

              {/* AI 추천 */}
              <div className="rounded-xl bg-gradient-to-br from-blue-50 to-white p-3 border border-blue-100 shadow-sm">
                <div className="text-[10px] text-blue-600/70 mb-1">AI 추천 Setpoint</div>
                <div className="text-xl font-black text-blue-700">
                  {cv.ai_recommendation ?? '-'}
                </div>
                <div className="text-[10px] text-blue-400">m/s</div>
              </div>
            </div>

            {/* 미니 실시간 차트 */}
            {chartData.length > 0 && (
              <div className="mb-4 rounded-xl bg-white p-3 border border-gray-100">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-bold text-sf-brown/60">실시간 전류 / 속도</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block" />전류</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-500 inline-block" />속도</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block border-dashed" />SP</span>
                </div>
                <RealtimeMultiLineCanvas
                  data={chartData}
                  lines={[
                    { dataKey: 'current', color: '#3b82f6', strokeWidth: 2, yAxisSide: 'left' },
                    { dataKey: 'speed', color: '#10b981', strokeWidth: 2, yAxisSide: 'right' },
                    { dataKey: 'setpoint', color: '#f59e0b', strokeWidth: 1.5, dashed: true, yAxisSide: 'right' },
                  ]}
                  width={580}
                  height={150}
                />
              </div>
            )}

            {/* 본 정보 */}
            {(detail.piece_info || currentPiece) && (
              <div className="flex items-center gap-4 text-[11px] text-sf-brown/60 bg-gray-50 rounded-xl p-3">
                <span>본 번호: <b className="text-sf-brown">#{(detail.piece_info || currentPiece).piece_no}</b></span>
                <span>제품규격: <b className="text-sf-brown">{(detail.piece_info || currentPiece).product_spec}</b></span>
                <span>진행률: <b className="text-emerald-600">{(detail.piece_info || currentPiece).progress}%</b></span>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-6 text-xs text-sf-brown/40">
            상세 데이터 없음
          </div>
        )}
      </div>
    </motion.div>
  );
}

function round4(v) {
  return Math.round(v * 10000) / 10000;
}
