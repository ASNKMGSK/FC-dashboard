// components/panels/analysis/AnalysisPanel.js
// 스마트팩토리 AI 플랫폼 - 상세 분석 패널 (리팩토링)

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  Calendar, TrendingUp,
  ChevronDown, MessageSquare,
  AlertTriangle, Brain, Target
} from 'lucide-react';
import SectionHeader from '@/components/SectionHeader';
import { DAYS_MAP } from './common/constants';

// H28: recharts 사용 탭은 dynamic import (SSR 비활성화, 코드 스플리팅)
const AnomalyTab = dynamic(() => import('./AnomalyTab'), { ssr: false });
const PredictionTab = dynamic(() => import('./PredictionTab'), { ssr: false });
const LifecycleTab = dynamic(() => import('./LifecycleTab'), { ssr: false });
const TrendTab = dynamic(() => import('./TrendTab'), { ssr: false });
// MaintenanceTab은 recharts 미사용이므로 정적 import
import MaintenanceTab from './MaintenanceTab';

// 분석 탭 정의
const ANALYSIS_TABS = [
  { key: 'anomaly', label: '이상탐지', icon: AlertTriangle },
  { key: 'prediction', label: '공정능력/예측', icon: Brain },
  { key: 'lifecycle', label: '롤 수명 관리', icon: Target },
  { key: 'trend', label: '생산 트렌드', icon: TrendingUp },
  { key: 'cs', label: '정비 분석', icon: MessageSquare },
];

// 생산라인/본 선택 + SPC 카드가 필요한 탭
const TABS_WITH_LINE_SELECTOR = ['anomaly', 'prediction'];

// 기간 옵션
const DATE_OPTIONS = [
  { value: '7d', label: '최근 7일' },
  { value: '30d', label: '최근 30일' },
  { value: '90d', label: '최근 90일' },
];


export default function AnalysisPanel({ auth, apiCall }) {
  const [activeTab, setActiveTab] = useState('anomaly');
  const [dateRange, setDateRange] = useState('7d');
  const [loading, setLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showDateDropdown, setShowDateDropdown] = useState(false);

  // API 데이터 상태
  const [summaryData, setSummaryData] = useState(null);
  const [csData, setCsData] = useState(null);
  const [dataLoaded, setDataLoaded] = useState(false);

  // SPC 2단계 검색 상태
  const [productionLines, setProductionLines] = useState([]);
  const [selectedLine, setSelectedLine] = useState(null);
  const [pieces, setPieces] = useState([]);
  const [selectedPiece, setSelectedPiece] = useState(null);
  const [pieceSpc, setPieceSpc] = useState(null);


  // 분석 데이터 상태
  const [anomalyData, setAnomalyData] = useState(null);
  const [predictionData, setPredictionData] = useState(null);
  const [lifecycleData, setCohortData] = useState(null);
  const [trendData, setTrendData] = useState(null);

  // 선택된 생산라인 ID ref (dateRange 변경 시 재검색용)

  // SPC 2단계: 생산라인 목록 로드
  useEffect(() => {
    if (!auth) return;
    apiCall({ endpoint: '/api/stands/production-lines', auth, timeoutMs: 10000 })
      .then(res => { if (res?.lines) setProductionLines(res.lines); })
      .catch(() => console.log('생산라인 목록 API 실패'));
  }, [auth, apiCall]);

  // SPC 2단계: 라인 선택 시 본 목록 로드 + selectedUser 자동 세팅
  useEffect(() => {
    if (!selectedLine) { setPieces([]); setSelectedPiece(null); setPieceSpc(null); setSelectedUser(null); return; }
    // 본 목록 로드
    apiCall({ endpoint: `/api/stands/production-lines/${selectedLine}/pieces`, auth, timeoutMs: 10000 })
      .then(res => { if (res?.pieces) setPieces(res.pieces); })
      .catch(() => console.log('본 목록 API 실패'));
    // 선택된 라인을 selectedUser로 매핑 (이상탐지/공정능력 탭에서 활용)
    const lineInfo = productionLines.find(l => l.id === selectedLine);
    if (lineInfo) {
      // 즉시 기본 정보 표시 (API 응답 전)
      setSelectedUser({
        id: lineInfo.id,
        segment: lineInfo.product_spec || 'H-beam',
        plan_tier: '가동중',
        monthly_yield: 0,
        product_count: 0,
        order_count: 0,
        top_equipment: [],
        stats: {},
        activity: [],
        model_predictions: {},
        period_stats: {},
        region: '사상압연',
      });
      // 백엔드에서 상세 데이터 로드
      const days = DAYS_MAP[dateRange] || 7;
      apiCall({ endpoint: `/api/production-lines/search?q=${encodeURIComponent(lineInfo.id)}&days=${days}`, auth, timeoutMs: 10000 })
        .then(res => {
          if (res?.status === 'success' && res.user) {
            const u = res.user;
            setSelectedUser({
              id: u.id,
              segment: u.segment || lineInfo.product_spec || 'H-beam',
              plan_tier: u.plan_tier || '가동중',
              monthly_yield: u.monthly_yield || 0,
              product_count: u.equipment_count || u.product_count || 0,
              order_count: u.work_order_count || u.order_count || 0,
              top_equipment: u.top_equipment || [],
              stats: u.stats || {},
              activity: u.activity || [],
              model_predictions: u.model_predictions || {},
              period_stats: u.period_stats || {},
              is_anomaly: u.is_anomaly,
              region: u.region || '사상압연',
            });
          }
        })
        .catch(() => console.log('생산라인 상세 데이터 조회 실패'));
    }
  }, [selectedLine, auth, apiCall, productionLines, dateRange]);

  // SPC 2단계: 본 선택 시 SPC 데이터 로드
  useEffect(() => {
    if (!selectedLine || !selectedPiece) { setPieceSpc(null); return; }
    apiCall({ endpoint: `/api/stands/production-lines/${selectedLine}/pieces/${selectedPiece}/spc`, auth, timeoutMs: 10000 })
      .then(res => { if (res?.status === 'success') setPieceSpc(res); })
      .catch(() => console.log('SPC 데이터 API 실패'));
  }, [selectedLine, selectedPiece, auth, apiCall]);

  // API 데이터 로드 (H30: Promise.all 병렬, M58: useEffect 통합)
  useEffect(() => {
    if (!auth) return;

    async function fetchData() {
      setLoading(true);
      const days = DAYS_MAP[dateRange] || 7;

      try {
        // H30: 독립 API 4개 병렬 호출
        const [summaryRes, anomalyRes, failureRes, lifecycleRes, trendRes] = await Promise.all([
          apiCall({ endpoint: `/api/stats/summary?days=${days}`, auth, timeoutMs: 10000 }).catch(() => null),
          apiCall({ endpoint: `/api/analysis/anomaly?days=${days}`, auth, timeoutMs: 10000 }).catch(() => null),
          apiCall({ endpoint: `/api/analysis/prediction/failure?days=${days}`, auth, timeoutMs: 10000 }).catch(() => null),
          apiCall({ endpoint: `/api/analysis/equipment/lifecycle?days=${days}`, auth, timeoutMs: 10000 }).catch(() => null),
          apiCall({ endpoint: `/api/analysis/trend/kpis?days=${days}`, auth, timeoutMs: 10000 }).catch(() => null),
        ]);

        // summary 처리
        if (summaryRes?.status === 'success') {
          setSummaryData(summaryRes);

          if (summaryRes.cs_stats_detail) {
            const channels = summaryRes.cs_stats_detail.map(stat => ({
              channel: stat.lang_name || stat.category || '기타',
              count: stat.total_count || 0,
              quality: stat.avg_quality?.toFixed(1) ?? '-',
              pending: stat.pending_count ?? 0,
            }));
            if (channels.length > 0) {
              setCsData({ channels, recent: [] });
            }
          }
        }

        // 이상탐지 처리
        if (anomalyRes?.status === 'success') {
          setAnomalyData({
            summary: anomalyRes.summary || {},
            by_type: anomalyRes.by_type || [],
            recent_alerts: anomalyRes.recent_alerts || [],
            trend: anomalyRes.trend || [],
          });
        }

        // 예측 처리
        if (failureRes?.status === 'success' && failureRes.failure) {
          setPredictionData({
            failure: failureRes.failure,
            production: failureRes.production || {},
            utilization: failureRes.utilization || {},
          });
        }

        // 설비 수명주기 처리
        if (lifecycleRes?.status === 'success' && lifecycleRes.retention) {
          setCohortData({
            retention: lifecycleRes.retention,
            rul_by_cohort: lifecycleRes.rul_by_cohort || [],
            production_flow: lifecycleRes.production_flow || lifecycleRes.conversion || [],
          });
        }

        // 트렌드 처리
        if (trendRes?.status === 'success' && trendRes.kpis) {
          setTrendData({
            kpis: trendRes.kpis,
            daily_metrics: trendRes.daily_metrics || [],
            correlation: trendRes.correlation || [],
            forecast: trendRes.forecast || [],
          });
        }

      } catch (e) {
        console.log('API 호출 실패');
      }
      setDataLoaded(true);
      setLoading(false);
    }

    fetchData();
  }, [auth, apiCall, dateRange]);


  return (
    <div>
      <SectionHeader
        title="상세 분석"
        subtitle="생산라인 · 설비 군집 · 수명주기 · 정비 데이터 심층 분석"
        right={
          <div className="flex items-center gap-2">
            {dataLoaded && (
              <span className={`rounded-full border-2 px-2 py-1 text-[10px] font-black ${
                summaryData
                  ? 'border-green-400/50 bg-green-50 text-green-700'
                  : 'border-red-400/50 bg-red-50 text-red-700'
              }`}>
                {summaryData ? 'LIVE' : 'NO DATA'}
              </span>
            )}
            {['anomaly', 'prediction', 'trend', 'lifecycle', 'cs'].includes(activeTab) && (
            <div className="relative">
              <button
                onClick={() => setShowDateDropdown(!showDateDropdown)}
                className="flex items-center gap-1.5 rounded-full border-2 border-sf-orange/20 bg-white/80 px-3 py-1.5 text-xs font-bold text-sf-brown hover:bg-sf-beige transition"
                aria-label="기간 선택"
              >
                <Calendar size={12} />
                {DATE_OPTIONS.find(d => d.value === dateRange)?.label}
                <ChevronDown size={12} />
              </button>
              {showDateDropdown && (
                <div className="absolute right-0 top-full mt-1 z-10 rounded-xl border-2 border-sf-orange/20 bg-white shadow-lg overflow-hidden">
                  {DATE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => { setDateRange(opt.value); setShowDateDropdown(false); }}
                      className={`block w-full px-4 py-2 text-left text-xs font-semibold hover:bg-sf-beige transition ${
                        dateRange === opt.value ? 'bg-sf-yellow/30 text-sf-brown' : 'text-sf-brown/70'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            )}
          </div>
        }
      />

      {/* 분석 유형 탭 */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2" role="tablist" aria-label="분석 유형">
        {ANALYSIS_TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm whitespace-nowrap transition-all ${
                isActive
                  ? 'bg-sf-beige text-sf-brown shadow-md'
                  : 'bg-white/80 border-2 border-sf-orange/20 text-sf-brown hover:bg-sf-beige'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* SPC 2단계 검색: 생산라인 → 본 번호 (이상탐지/공정능력 탭에서만 표시) */}
      {TABS_WITH_LINE_SELECTOR.includes(activeTab) && (
      <div className="flex gap-4 mb-4 items-center flex-wrap">
        <div>
          <label className="text-[10px] font-bold text-sf-brown/60 block mb-1">생산라인</label>
          <select
            value={selectedLine || ''}
            onChange={e => { setSelectedLine(e.target.value || null); setSelectedPiece(null); setPieceSpc(null); }}
            className="rounded-xl border-2 border-sf-orange/20 px-3 py-2 text-sm bg-white focus:border-sf-orange focus:outline-none"
          >
            <option value="">라인 선택</option>
            {productionLines.map(l => (
              <option key={l.id} value={l.id}>{l.name} ({l.product_spec})</option>
            ))}
          </select>
        </div>

        {selectedLine && pieces.length > 0 && (
          <div>
            <label className="text-[10px] font-bold text-sf-brown/60 block mb-1">본 번호</label>
            <select
              value={selectedPiece || ''}
              onChange={e => setSelectedPiece(e.target.value || null)}
              className="rounded-xl border-2 border-sf-orange/20 px-3 py-2 text-sm bg-white focus:border-sf-orange focus:outline-none"
            >
              <option value="">본 선택</option>
              {pieces.map(p => (
                <option key={p.piece_no} value={p.piece_no}>
                  #{p.piece_no} ({p.product_spec}) - 완료
                </option>
              ))}
            </select>
          </div>
        )}

        {selectedLine && selectedPiece && (
          <div className="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-2 rounded-xl border border-emerald-200">
            {productionLines.find(l => l.id === selectedLine)?.name} / #{selectedPiece}본
          </div>
        )}
      </div>
      )}

      {/* SPC 요약 카드 (이상탐지/공정능력 탭에서만 표시) */}
      {TABS_WITH_LINE_SELECTOR.includes(activeTab) && pieceSpc && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="rounded-xl border-2 border-sf-orange/10 bg-white p-3">
            <div className="text-[10px] font-bold text-sf-brown/50 mb-1">공정능력 (Cpk)</div>
            <div className={`text-xl font-black ${pieceSpc.capability.cpk >= 1.33 ? 'text-emerald-600' : pieceSpc.capability.cpk >= 1.0 ? 'text-amber-600' : 'text-red-600'}`}>
              {pieceSpc.capability.cpk}
            </div>
          </div>
          <div className="rounded-xl border-2 border-sf-orange/10 bg-white p-3">
            <div className="text-[10px] font-bold text-sf-brown/50 mb-1">평균 (X-bar)</div>
            <div className="text-xl font-black text-sf-brown">{pieceSpc.capability.mean}</div>
          </div>
          <div className="rounded-xl border-2 border-sf-orange/10 bg-white p-3">
            <div className="text-[10px] font-bold text-sf-brown/50 mb-1">표준편차</div>
            <div className="text-xl font-black text-sf-brown">{pieceSpc.capability.std}</div>
          </div>
          <div className="rounded-xl border-2 border-sf-orange/10 bg-white p-3">
            <div className="text-[10px] font-bold text-sf-brown/50 mb-1">불량률 요약</div>
            <div className="text-xs space-y-0.5">
              <div className="flex justify-between"><span className="text-sf-brown/60">두께</span><span className="font-bold text-red-500">{pieceSpc.defect_summary.thickness_defect}%</span></div>
              <div className="flex justify-between"><span className="text-sf-brown/60">표면</span><span className="font-bold text-amber-500">{pieceSpc.defect_summary.surface_defect}%</span></div>
              <div className="flex justify-between"><span className="text-sf-brown/60">형상</span><span className="font-bold text-blue-500">{pieceSpc.defect_summary.shape_defect}%</span></div>
              <div className="flex justify-between"><span className="text-sf-brown/60">폭</span><span className="font-bold text-purple-500">{pieceSpc.defect_summary.width_defect}%</span></div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'anomaly' && (
        <AnomalyTab selectedUser={selectedUser} anomalyData={anomalyData} apiCall={apiCall} auth={auth} pieceSpc={pieceSpc} />
      )}

      {activeTab === 'prediction' && (
        <PredictionTab
          predictionData={predictionData}
          apiCall={apiCall}
          auth={auth}
          dateRange={dateRange}
          pieceSpc={pieceSpc}
        />
      )}

      {activeTab === 'lifecycle' && (
        <LifecycleTab lifecycleData={lifecycleData} />
      )}

      {activeTab === 'trend' && (
        <TrendTab trendData={trendData} />
      )}

      {activeTab === 'cs' && (
        <MaintenanceTab csData={csData} />
      )}

    </div>
  );
}
