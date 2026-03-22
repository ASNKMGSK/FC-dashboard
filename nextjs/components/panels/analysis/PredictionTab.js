// components/panels/analysis/PredictionTab.js
// 예측 분석 탭 (H29: 자체 상태 관리) + SPC 공정능력 지수

import { useState, useCallback, useEffect } from 'react';
import toast from 'react-hot-toast';
import {
  Brain, AlertTriangle, BarChart3, Activity,
  ArrowUpRight, Gauge
} from 'lucide-react';
import EquipmentSearchInput from './common/EquipmentSearchInput';
import AnalysisEmptyState from './common/EmptyState';
import { DAYS_MAP } from './common/constants';

function getCpkColor(val) {
  if (val == null) return '#9CA3AF';
  if (val >= 1.33) return '#16A34A';
  if (val >= 1.0) return '#CA8A04';
  return '#DC2626';
}

function getCpkLabel(val) {
  if (val == null) return '데이터 없음';
  if (val >= 1.33) return '우수 — 두께 산포 안정';
  if (val >= 1.0) return '보통 — 롤갭 미세 조정 권장';
  return '개선 필요 — 롤갭/AGC 점검 필요';
}

export default function PredictionTab({
  predictionData, apiCall, auth, dateRange, pieceSpc,
}) {
  const [predictionTab, setPredictionTab] = useState('failure');
  const [predictionSearchQuery, setPredictionSearchQuery] = useState('');
  const [predictionUser, setPredictionUser] = useState(null);
  const [predictionUserLoading, setPredictionUserLoading] = useState(false);
  const [capData, setCapData] = useState(null);
  const [capLoading, setCapLoading] = useState(false);

  // pieceSpc가 있으면 해당 본의 공정능력 데이터 사용, 없으면 전체 SPC API 호출
  useEffect(() => {
    if (pieceSpc?.capability) {
      setCapData(pieceSpc.capability);
      setCapLoading(false);
      return;
    }
    if (!apiCall) return;
    setCapLoading(true);
    apiCall({ endpoint: '/api/spc/capability', auth, timeoutMs: 10000 })
      .then(res => {
        if (res?.status === 'success' && res.data) setCapData(res.data);
        else setCapData(null);
      })
      .catch(() => setCapData(null))
      .finally(() => setCapLoading(false));
  }, [apiCall, auth, pieceSpc]);

  const handlePredictionSearch = useCallback(async (userId) => {
    const id = (userId || predictionSearchQuery).trim();
    if (!id) { toast.error('생산라인 ID를 입력하세요'); return; }
    setPredictionUserLoading(true);
    const days = DAYS_MAP[dateRange] || 7;
    try {
      const res = await apiCall({
        endpoint: `/api/production-lines/search?q=${encodeURIComponent(id)}&days=${days}`,
        auth,
        timeoutMs: 10000,
      });
      if (res?.status === 'success' && res.user) {
        setPredictionUser({
          id: res.user.id,
          segment: res.user.segment,
          plan_tier: res.user.plan_tier || res.user.grade,
          monthly_yield: res.user.monthly_yield || 0,
          model_predictions: res.user.model_predictions || {},
        });
        toast.success(`${res.user.id} 예측 결과를 불러왔습니다`);
      } else {
        toast.error('생산라인을 찾을 수 없습니다');
        setPredictionUser(null);
      }
    } catch (e) {
      toast.error('생산라인 검색에 실패했습니다');
      setPredictionUser(null);
    }
    setPredictionUserLoading(false);
  }, [apiCall, auth, dateRange, predictionSearchQuery]);

  return (
    <div className="space-y-6">
      {/* 개별 설비 예측 검색 (M57: EquipmentSearchInput 공통 컴포넌트) */}
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="flex items-center gap-2 mb-3">
          <Brain size={16} className="text-sf-orange" />
          <span className="text-sm font-black text-sf-brown">개별 설비 예측 조회</span>
        </div>
        <EquipmentSearchInput
          value={predictionSearchQuery}
          onChange={setPredictionSearchQuery}
          onSearch={handlePredictionSearch}
          loading={predictionUserLoading}
          buttonLabel="예측"
          loadingLabel="조회중..."
        />
      </div>

      {/* SPC 공정능력 지수 */}
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="flex items-center gap-2 mb-4">
          <Gauge size={18} className="text-sf-orange" />
          <span className="text-sm font-black text-sf-brown">
            {pieceSpc ? `두께 공정능력 지수 — ${pieceSpc.product_spec || 'H300×300'} #${pieceSpc.piece_no}본` : '두께 공정능력 지수'}
          </span>
        </div>
        {capLoading ? (
          <div className="flex items-center justify-center h-24 text-sm text-sf-brown/50">공정능력 데이터 로딩 중...</div>
        ) : !capData ? (
          <div className="flex items-center justify-center h-24 text-sm text-sf-brown/50">공정능력 데이터가 없습니다</div>
        ) : (
          <div className="space-y-4">
            {/* Cpk 메인 게이지 */}
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-5xl font-black" style={{ color: getCpkColor(capData.cpk) }}>
                  {capData.cpk != null ? capData.cpk.toFixed(2) : '-'}
                </div>
                <div className="text-xs font-bold mt-1" style={{ color: getCpkColor(capData.cpk) }}>
                  Cpk · {getCpkLabel(capData.cpk)}
                </div>
              </div>
              <div className="flex-1 grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-sf-orange/20 bg-sf-beige/30 p-3 text-center">
                  <div className="text-lg font-black text-sf-brown">{capData.cp != null ? capData.cp.toFixed(2) : '-'}</div>
                  <div className="text-[10px] text-sf-brown/60 font-bold">Cp</div>
                </div>
                <div className="rounded-xl border border-sf-orange/20 bg-sf-beige/30 p-3 text-center">
                  <div className="text-lg font-black text-sf-brown">{capData.pp != null ? capData.pp.toFixed(2) : '-'}</div>
                  <div className="text-[10px] text-sf-brown/60 font-bold">Pp</div>
                </div>
                <div className="rounded-xl border border-sf-orange/20 bg-sf-beige/30 p-3 text-center">
                  <div className="text-lg font-black text-sf-brown">{capData.ppk != null ? capData.ppk.toFixed(2) : '-'}</div>
                  <div className="text-[10px] text-sf-brown/60 font-bold">Ppk</div>
                </div>
              </div>
            </div>
            {/* 스펙 정보 */}
            <div className="grid grid-cols-4 gap-2">
              <div className="rounded-lg bg-blue-50 border border-blue-200 p-2 text-center">
                <div className="text-xs font-bold text-blue-700">USL</div>
                <div className="text-sm font-black text-blue-600">{capData.usl != null ? `${capData.usl}mm` : '300.5mm'}</div>
              </div>
              <div className="rounded-lg bg-green-50 border border-green-200 p-2 text-center">
                <div className="text-xs font-bold text-green-700">Target</div>
                <div className="text-sm font-black text-green-600">{capData.target != null ? `${capData.target}mm` : '300.0mm'}</div>
              </div>
              <div className="rounded-lg bg-blue-50 border border-blue-200 p-2 text-center">
                <div className="text-xs font-bold text-blue-700">LSL</div>
                <div className="text-sm font-black text-blue-600">{capData.lsl != null ? `${capData.lsl}mm` : '299.5mm'}</div>
              </div>
              <div className="rounded-lg bg-gray-50 border border-gray-200 p-2 text-center">
                <div className="text-xs font-bold text-gray-700">Mean/Std</div>
                <div className="text-sm font-black text-gray-600">{capData.mean != null ? capData.mean.toFixed(1) : '-'}/{capData.std != null ? capData.std.toFixed(2) : '-'}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 개별 설비 예측 결과 */}
      {predictionUser?.model_predictions && (
        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Brain size={18} className="text-sf-orange" />
              <span className="text-sm font-black text-sf-brown">{predictionUser.id} ML 예측 결과</span>
              <span className="px-2 py-0.5 rounded-full bg-sf-beige text-xs font-semibold text-sf-brown">
                {predictionUser.segment} · {predictionUser.plan_tier}
              </span>
            </div>
            <button
              onClick={() => setPredictionUser(null)}
              className="text-xs text-sf-brown/50 hover:text-sf-brown transition-all"
            >
              닫기
            </button>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {predictionUser.model_predictions.failure && (
              <div className={`rounded-2xl p-4 border-2 ${
                predictionUser.model_predictions.failure.risk_code >= 2 ? 'border-red-300 bg-red-50' :
                predictionUser.model_predictions.failure.risk_code === 1 ? 'border-orange-300 bg-orange-50' :
                'border-green-300 bg-green-50'
              }`}>
                <div className="text-xs font-bold text-sf-brown mb-1">고장 확률</div>
                <div className="text-2xl font-black" style={{
                  color: predictionUser.model_predictions.failure.risk_code >= 2 ? '#DC2626' :
                         predictionUser.model_predictions.failure.risk_code === 1 ? '#EA580C' : '#16A34A'
                }}>{predictionUser.model_predictions.failure.probability}%</div>
                <div className="text-xs text-sf-brown/60">{predictionUser.model_predictions.failure.risk_level}</div>
              </div>
            )}
            {predictionUser.model_predictions.yield && (() => {
              const yieldData = predictionUser.model_predictions.yield;
              return (
              <div className="rounded-2xl p-4 border-2 border-purple-300 bg-purple-50">
                <div className="text-xs font-bold text-sf-brown mb-1">예상 월생산량</div>
                <div className="text-2xl font-black text-purple-600">
                  {yieldData.predicted_next_month >= 10000
                    ? `${(yieldData.predicted_next_month / 10000).toFixed(0)}만톤`
                    : `${(yieldData.predicted_next_month || 0).toLocaleString()}톤`}
                </div>
                <div className="text-xs text-sf-brown/60">성장률 {yieldData.growth_rate}%</div>
              </div>
              );
            })()}
            {predictionUser.model_predictions.defect && (
              <div className={`rounded-2xl p-4 border-2 ${
                predictionUser.model_predictions.defect.is_anomaly ? 'border-red-300 bg-red-50' : 'border-green-300 bg-green-50'
              }`}>
                <div className="text-xs font-bold text-sf-brown mb-1">이상 패턴</div>
                <div className="text-2xl font-black" style={{
                  color: predictionUser.model_predictions.defect.is_anomaly ? '#DC2626' : '#16A34A'
                }}>{predictionUser.model_predictions.defect.risk_level}</div>
                <div className="text-xs text-sf-brown/60">점수 {(predictionUser.model_predictions.defect.anomaly_score * 100).toFixed(1)}%</div>
              </div>
            )}
            {predictionUser.model_predictions.maintenance_quality && (() => {
              const mqData = predictionUser.model_predictions.maintenance_quality;
              return (
              <div className={`rounded-2xl p-4 border-2 ${
                mqData.score >= 80 ? 'border-green-300 bg-green-50' :
                mqData.score >= 50 ? 'border-yellow-300 bg-yellow-50' :
                'border-red-300 bg-red-50'
              }`}>
                <div className="text-xs font-bold text-sf-brown mb-1">정비 품질</div>
                <div className="text-2xl font-black" style={{
                  color: mqData.score >= 80 ? '#16A34A' :
                         mqData.score >= 50 ? '#CA8A04' : '#DC2626'
                }}>{mqData.score}점</div>
                <div className="text-xs text-sf-brown/60">{mqData.grade}</div>
              </div>
              );
            })()}
            {predictionUser.model_predictions.segment && (
              <div className="rounded-2xl p-4 border-2 border-blue-300 bg-blue-50">
                <div className="text-xs font-bold text-sf-brown mb-1">설비등급</div>
                <div className="text-lg font-black text-blue-600">{predictionUser.model_predictions.segment.segment_name}</div>
                <div className="text-xs text-sf-brown/60">클러스터 #{predictionUser.model_predictions.segment.cluster}</div>
              </div>
            )}
          </div>
          {/* SHAP 요인 */}
          {predictionUser.model_predictions.failure?.factors?.length > 0 && (
            <div className="mt-4">
              <div className="text-xs font-bold text-sf-brown mb-2">고장 주요 요인 (SHAP)</div>
              <div className="space-y-2">
                {predictionUser.model_predictions.failure.factors.map((f, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-sf-orange text-white text-xs font-bold flex items-center justify-center shrink-0">
                      {i + 1}
                    </span>
                    <span className="text-xs font-semibold text-sf-brown w-24">{f.factor}</span>
                    <div className="flex-1 h-2 bg-sf-beige rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-sf-yellow to-sf-orange"
                        style={{ width: `${Math.min(100, f.importance * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-bold text-sf-orange w-10 text-right">{(f.importance * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {!predictionData ? (
        <AnalysisEmptyState
          icon={Brain}
          title="예측 데이터를 불러올 수 없습니다"
          subtitle="백엔드 API 연결을 확인하세요"
        />
      ) : (
      <>
      {/* 예측 유형 선택 */}
      <div className="flex gap-2">
        {[
          { key: 'failure', label: '고장 예측', icon: AlertTriangle },
          { key: 'production', label: '생산량 예측', icon: BarChart3 },
          { key: 'utilization', label: '설비 가동 예측', icon: Activity },
        ].map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setPredictionTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                predictionTab === tab.key
                  ? 'bg-sf-brown text-white'
                  : 'bg-white border-2 border-sf-orange/20 text-sf-brown hover:bg-sf-beige'
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 고장 예측 */}
      {predictionTab === 'failure' && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-2xl border-2 border-red-200 bg-red-50 p-4">
              <div className="text-xs font-bold text-red-700 mb-1">고위험 고장</div>
              <div className="text-2xl font-black text-red-600">{predictionData.failure.high_risk_count}</div>
              <div className="text-xs text-red-600/70">설비</div>
            </div>
            <div className="rounded-2xl border-2 border-orange-200 bg-orange-50 p-4">
              <div className="text-xs font-bold text-orange-700 mb-1">중위험 고장</div>
              <div className="text-2xl font-black text-orange-600">{predictionData.failure.medium_risk_count}</div>
              <div className="text-xs text-orange-600/70">설비</div>
            </div>
            <div className="rounded-2xl border-2 border-green-200 bg-green-50 p-4">
              <div className="text-xs font-bold text-green-700 mb-1">안전</div>
              <div className="text-2xl font-black text-green-600">{predictionData.failure.low_risk_count}</div>
              <div className="text-xs text-green-600/70">설비</div>
            </div>
            <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-4">
              <div className="text-xs font-bold text-sf-brown mb-1">모델 정확도</div>
              <div className="text-2xl font-black text-sf-brown">{predictionData.failure.model_accuracy}%</div>
              <div className="text-xs text-sf-brown/60">F1 Score</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
              <div className="mb-4 text-sm font-black text-sf-brown">고장 예측 주요 요인</div>
              <div className="space-y-3">
                {predictionData.failure.top_factors.map((factor, idx) => (
                  <div key={idx} className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-sf-orange text-white text-xs font-bold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span className="text-sm font-semibold text-sf-brown">{factor.factor}</span>
                        <span className="text-sm font-bold text-sf-orange">{(factor.importance * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-2 bg-sf-beige rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-sf-yellow to-sf-orange"
                          style={{ width: `${factor.importance * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
              <div className="mb-4 text-sm font-black text-sf-brown">고장 고위험 설비</div>
              <div className="space-y-3">
                {(predictionData.failure?.high_risk_users || []).map((user, idx) => (
                  <div key={idx} className="flex items-center gap-4 p-3 rounded-2xl bg-red-50 border border-red-200">
                    <div className="w-10 h-10 rounded-full bg-red-500 text-white font-bold flex items-center justify-center text-sm">
                      {user.probability}%
                    </div>
                    <div className="flex-1">
                      <div className="font-bold text-sf-brown">{user.id}</div>
                      <div className="text-xs text-sf-brown/60">{user.segment}</div>
                    </div>
                    <div className="text-xs text-red-600 font-semibold">{user.last_active}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* 생산량 예측 */}
      {predictionTab === 'production' && predictionData?.production && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-2xl border-2 border-green-200 bg-green-50 p-4">
            <div className="text-xs font-bold text-green-700 mb-1">예상 월생산량</div>
            <div className="text-xl font-black text-green-600">{((predictionData.production.predicted_monthly || 0) / 10000).toFixed(0)}만톤</div>
            <div className="flex items-center gap-1 text-xs text-green-600">
              <ArrowUpRight size={12} />+{predictionData.production.growth_rate || 0}%
            </div>
          </div>
          <div className="rounded-2xl border-2 border-blue-200 bg-blue-50 p-4">
            <div className="text-xs font-bold text-blue-700 mb-1">설비당 평균 생산량</div>
            <div className="text-xl font-black text-blue-600">{(predictionData.production.per_equipment_output || 0).toLocaleString()}</div>
            <div className="text-xs text-blue-600/70">설비당 평균</div>
          </div>
          <div className="rounded-2xl border-2 border-purple-200 bg-purple-50 p-4">
            <div className="text-xs font-bold text-purple-700 mb-1">주요 설비 평균 생산량</div>
            <div className="text-xl font-black text-purple-600">{(predictionData.production.per_active_equipment_output || 0).toLocaleString()}</div>
            <div className="text-xs text-purple-600/70">가동 설비 평균</div>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-4">
            <div className="text-xs font-bold text-sf-brown mb-1">신뢰도</div>
            <div className="text-xl font-black text-sf-brown">{predictionData.production.confidence || 0}%</div>
            <div className="text-xs text-sf-brown/60">예측 정확도</div>
          </div>
          <div className="rounded-2xl border-2 border-pink-200 bg-pink-50 p-4 col-span-2 lg:col-span-1">
            <div className="text-xs font-bold text-pink-700 mb-1">Enterprise</div>
            <div className="text-xl font-black text-pink-600">{predictionData.production.grade_a_count || 0}대</div>
            <div className="text-xs text-pink-600/70">대형 설비</div>
          </div>
          <div className="rounded-2xl border-2 border-cyan-200 bg-cyan-50 p-4 col-span-2 lg:col-span-1">
            <div className="text-xs font-bold text-cyan-700 mb-1">Premium</div>
            <div className="text-xl font-black text-cyan-600">{predictionData.production.grade_b_count || 0}대</div>
            <div className="text-xs text-cyan-600/70">중형 설비</div>
          </div>
          <div className="rounded-2xl border-2 border-teal-200 bg-teal-50 p-4 col-span-2">
            <div className="text-xs font-bold text-teal-700 mb-1">Standard</div>
            <div className="text-xl font-black text-teal-600">{predictionData.production.grade_c_count || 0}대</div>
            <div className="text-xs text-teal-600/70">소형 설비</div>
          </div>
        </div>
      )}

      {/* 참여도 예측 */}
      {predictionTab === 'utilization' && predictionData?.utilization && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="rounded-2xl border-2 border-blue-200 bg-blue-50 p-4">
            <div className="text-xs font-bold text-blue-700 mb-1">일일 가동 설비</div>
            <div className="text-2xl font-black text-blue-600">{predictionData.utilization.daily_active_equipment || 0}대</div>
            <div className="text-xs text-blue-600/70">예상 일일 가동</div>
          </div>
          <div className="rounded-2xl border-2 border-indigo-200 bg-indigo-50 p-4">
            <div className="text-xs font-bold text-indigo-700 mb-1">월간 가동 설비</div>
            <div className="text-2xl font-black text-indigo-600">{predictionData.utilization.monthly_active_equipment || 0}대</div>
            <div className="text-xs text-indigo-600/70">예상 월간 가동</div>
          </div>
          <div className="rounded-2xl border-2 border-violet-200 bg-violet-50 p-4">
            <div className="text-xs font-bold text-violet-700 mb-1">가동률</div>
            <div className="text-2xl font-black text-violet-600">{predictionData.utilization.utilization_rate || 0}%</div>
            <div className="text-xs text-violet-600/70">일일/월간 비율</div>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-4">
            <div className="text-xs font-bold text-sf-brown mb-1">평균 가동시간</div>
            <div className="text-2xl font-black text-sf-brown">{predictionData.utilization.avg_session || 0}시간</div>
            <div className="text-xs text-sf-brown/60">설비당 일일 가동</div>
          </div>
          <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-4 col-span-2">
            <div className="text-xs font-bold text-sf-brown mb-1">일일 사이클 수</div>
            <div className="text-2xl font-black text-sf-brown">{predictionData.utilization.sessions_per_day || 0}</div>
            <div className="text-xs text-sf-brown/60">설비당 평균 생산 사이클</div>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}
