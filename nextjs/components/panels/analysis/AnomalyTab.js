// components/panels/analysis/AnomalyTab.js
// 이상탐지 분석 탭 + SPC X-bar/R 관리도

import { useState, useEffect } from 'react';
import { AlertTriangle, Shield, Eye, Activity, Zap } from 'lucide-react';
import CustomTooltip from '@/components/common/CustomTooltip';
import { getSeverityClasses } from '@/components/common/constants';
import AnalysisEmptyState from './common/EmptyState';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, AreaChart, Area, Cell,
  LineChart, Line, ReferenceLine
} from 'recharts';

function SpcOutOfControlDot({ cx, cy, payload, dataKey, ucl, lcl }) {
  const val = payload?.[dataKey];
  if (val == null || ucl == null || lcl == null) return null;
  const isOut = val > ucl || val < lcl;
  return (
    <circle cx={cx} cy={cy} r={isOut ? 5 : 3}
      fill={isOut ? '#EF4444' : '#3B82F6'}
      stroke={isOut ? '#DC2626' : '#2563EB'}
      strokeWidth={isOut ? 2 : 1}
    />
  );
}

export default function AnomalyTab({ selectedEquipmentLine, anomalyData, apiCall, auth, pieceSpc }) {
  const [spcData, setSpcData] = useState(null);
  const [spcDays, setSpcDays] = useState(30);
  const [spcLoading, setSpcLoading] = useState(false);

  // pieceSpc가 있으면 해당 본의 X-bar/R 데이터 사용, 없으면 전체 SPC API 호출
  useEffect(() => {
    if (pieceSpc?.xbar_chart) {
      // 2단계 검색으로 선택한 본의 SPC 데이터 활용
      const chart = pieceSpc.xbar_chart;
      const mapped = (chart.data || []).map(d => ({
        date: `#${d.subgroup}`,
        xbar: d.xbar,
        range: d.range,
        ucl: chart.ucl,
        lcl: chart.lcl,
        cl: chart.cl,
        ucl_r: chart.ucl_r,
        lcl_r: chart.lcl_r,
        cl_r: chart.cl_r,
      }));
      setSpcData(mapped);
      setSpcLoading(false);
      return;
    }
    if (!apiCall) return;
    setSpcLoading(true);
    apiCall({ endpoint: `/api/spc/xbar-chart?days=${spcDays}`, auth, timeoutMs: 10000 })
      .then(res => {
        if (res?.status === 'success' && res.data) setSpcData(res.data);
        else setSpcData(null);
      })
      .catch(() => setSpcData(null))
      .finally(() => setSpcLoading(false));
  }, [apiCall, auth, spcDays, pieceSpc]);

  return (
    <div className="space-y-6">
      {/* SPC X-bar 관리도 */}
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-sf-orange" />
            <span className="text-sm font-black text-sf-brown">
              {pieceSpc ? `두께 X-bar 관리도 — ${pieceSpc.product_spec || 'H300×300'} #${pieceSpc.piece_no}본` : '두께 X-bar 관리도 (H300×300)'}
            </span>
          </div>
          {!pieceSpc && (
            <select
              value={spcDays}
              onChange={e => setSpcDays(Number(e.target.value))}
              className="text-xs border-2 border-sf-orange/20 rounded-lg px-2 py-1 bg-white text-sf-brown font-semibold"
            >
              <option value={7}>7일</option>
              <option value={14}>14일</option>
              <option value={30}>30일</option>
              <option value={90}>90일</option>
            </select>
          )}
        </div>
        {spcLoading ? (
          <div className="flex items-center justify-center h-48 text-sm text-sf-brown/50">SPC 데이터 로딩 중...</div>
        ) : !spcData || spcData.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-sm text-sf-brown/50">SPC 데이터가 없습니다</div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={spcData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
                <XAxis dataKey="date" tick={{ fill: '#5C4A3D', fontSize: 10 }} />
                <YAxis tick={{ fill: '#5C4A3D', fontSize: 11 }} domain={['auto', 'auto']} label={{ value: '두께 (mm)', angle: -90, position: 'insideLeft', fill: '#5C4A3D', fontSize: 11 }} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={spcData[0]?.ucl} stroke="#EF4444" strokeDasharray="6 3" label={{ value: 'UCL', position: 'right', fill: '#EF4444', fontSize: 10 }} />
                <ReferenceLine y={spcData[0]?.lcl} stroke="#EF4444" strokeDasharray="6 3" label={{ value: 'LCL', position: 'right', fill: '#EF4444', fontSize: 10 }} />
                <ReferenceLine y={spcData[0]?.cl} stroke="#16A34A" label={{ value: 'CL', position: 'right', fill: '#16A34A', fontSize: 10 }} />
                <Line type="monotone" dataKey="xbar" name="X-bar" stroke="#3B82F6" strokeWidth={2}
                  dot={<SpcOutOfControlDot dataKey="xbar" ucl={spcData[0]?.ucl} lcl={spcData[0]?.lcl} />}
                />
              </LineChart>
            </ResponsiveContainer>

            {/* R 관리도 */}
            <div className="mt-4">
              <div className="text-xs font-black text-sf-brown mb-2">R 관리도 (범위)</div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={spcData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
                  <XAxis dataKey="date" tick={{ fill: '#5C4A3D', fontSize: 10 }} />
                  <YAxis tick={{ fill: '#5C4A3D', fontSize: 11 }} domain={['auto', 'auto']} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine y={spcData[0]?.ucl_r} stroke="#EF4444" strokeDasharray="6 3" label={{ value: 'UCL_R', position: 'right', fill: '#EF4444', fontSize: 10 }} />
                  <ReferenceLine y={spcData[0]?.lcl_r} stroke="#EF4444" strokeDasharray="6 3" label={{ value: 'LCL_R', position: 'right', fill: '#EF4444', fontSize: 10 }} />
                  <ReferenceLine y={spcData[0]?.cl_r} stroke="#16A34A" label={{ value: 'CL_R', position: 'right', fill: '#16A34A', fontSize: 10 }} />
                  <Line type="monotone" dataKey="range" name="Range" stroke="#F59E0B" strokeWidth={2}
                    dot={<SpcOutOfControlDot dataKey="range" ucl={spcData[0]?.ucl_r} lcl={spcData[0]?.lcl_r} />}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
      {/* 선택된 설비 이상탐지 결과 */}
      {selectedEquipmentLine?.model_predictions?.defect && (
        <div className={`rounded-3xl border-2 p-5 shadow-sm backdrop-blur ${
          selectedEquipmentLine.model_predictions.defect.is_anomaly ? 'border-red-300 bg-red-50/80' : 'border-green-300 bg-green-50/80'
        }`}>
          <div className="flex items-center gap-2 mb-3">
            <Shield size={18} className={selectedEquipmentLine.model_predictions.defect.is_anomaly ? 'text-red-600' : 'text-green-600'} />
            <span className="text-sm font-black text-sf-brown">{selectedEquipmentLine.id} 이상 패턴 탐지 결과</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-2xl font-black" style={{
                color: selectedEquipmentLine.model_predictions.defect.is_anomaly ? '#DC2626' : '#16A34A'
              }}>{(selectedEquipmentLine.model_predictions.defect.anomaly_score * 100).toFixed(1)}%</div>
              <div className="text-xs text-sf-brown/60">이상 점수</div>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-black ${
                selectedEquipmentLine.model_predictions.defect.is_anomaly ? 'text-red-600' : 'text-green-600'
              }`}>
                {selectedEquipmentLine.model_predictions.defect.risk_level}
              </div>
              <div className="text-xs text-sf-brown/60">판정</div>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-sf-brown/40">{selectedEquipmentLine.model_predictions.defect.model}</div>
        </div>
      )}
      {!anomalyData ? (
        <AnalysisEmptyState
          icon={AlertTriangle}
          title="이상탐지 데이터를 불러올 수 없습니다"
          subtitle="백엔드 API 연결을 확인하세요"
        />
      ) : (
      <>
      {/* 이상탐지 요약 카드 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border-2 border-red-200 bg-red-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={18} className="text-red-500" />
            <span className="text-xs font-bold text-red-700">고위험</span>
          </div>
          <div className="text-2xl font-black text-red-600">{anomalyData.summary?.high_risk || 0}</div>
          <div className="text-xs text-red-600/70">즉시 조치 필요</div>
        </div>
        <div className="rounded-2xl border-2 border-orange-200 bg-orange-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Shield size={18} className="text-orange-500" />
            <span className="text-xs font-bold text-orange-700">중위험</span>
          </div>
          <div className="text-2xl font-black text-orange-600">{anomalyData.summary?.medium_risk || 0}</div>
          <div className="text-xs text-orange-600/70">모니터링 필요</div>
        </div>
        <div className="rounded-2xl border-2 border-yellow-200 bg-yellow-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Eye size={18} className="text-yellow-600" />
            <span className="text-xs font-bold text-yellow-700">저위험</span>
          </div>
          <div className="text-2xl font-black text-yellow-600">{anomalyData.summary?.low_risk || 0}</div>
          <div className="text-xs text-yellow-600/70">관찰 대상</div>
        </div>
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity size={18} className="text-sf-orange" />
            <span className="text-xs font-bold text-sf-brown">탐지율</span>
          </div>
          <div className="text-2xl font-black text-sf-brown">{anomalyData.summary?.anomaly_rate || 0}%</div>
          <div className="text-xs text-sf-brown/60">{anomalyData.summary?.anomaly_count || 0}/{anomalyData.summary?.total_equipment || 0}</div>
        </div>
      </div>

      {/* 이상유형별 분포 & 트렌드 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="mb-4 text-sm font-black text-sf-brown">이상 유형별 분포</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={anomalyData.by_type || []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <YAxis type="category" dataKey="type" tick={{ fill: '#5C4A3D', fontSize: 10 }} width={120} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="탐지 수" radius={[0, 4, 4, 0]}>
                {(anomalyData.by_type || []).map((entry, idx) => (
                  <Cell key={idx} fill={entry.severity === 'high' ? '#EF4444' : entry.severity === 'medium' ? '#F97316' : '#EAB308'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="mb-4 text-sm font-black text-sf-brown">일별 이상 탐지 트렌드</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={anomalyData.trend || []}>
              <defs>
                <linearGradient id="anomaly-colorAnomaly" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
              <XAxis dataKey="date" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <YAxis tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="count" name="탐지 수" stroke="#EF4444" fill="url(#anomaly-colorAnomaly)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 최근 알림 */}
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={18} className="text-red-500" />
          <span className="text-sm font-black text-sf-brown">실시간 이상 탐지 알림</span>
        </div>
        <div className="space-y-3">
          {(anomalyData.recent_alerts || []).map((alert, idx) => {
            const sc = getSeverityClasses(alert.severity);
            return (
            <div key={idx} className={`flex items-center gap-4 p-4 rounded-2xl border-2 ${sc.border} ${sc.bg}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${sc.icon}`}>
                <AlertTriangle size={18} className="text-white" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-sf-brown">{alert.id}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${sc.badge}`}>{alert.type}</span>
                </div>
                <p className="text-sm text-sf-brown/70">{alert.detail}</p>
              </div>
              <div className="text-xs text-sf-brown/50">{alert.time}</div>
            </div>
            );
          })}
        </div>
      </div>
      </>
      )}
    </div>
  );
}
