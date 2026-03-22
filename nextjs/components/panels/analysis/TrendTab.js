// components/panels/analysis/TrendTab.js
// 트렌드 분석 탭

import {
  TrendingUp, ArrowUpRight, ArrowDownRight, Brain, BarChart3
} from 'lucide-react';
import CustomTooltip from '@/components/common/CustomTooltip';
import AnalysisEmptyState from './common/EmptyState';
import {
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, LineChart, Line, ComposedChart, Area
} from 'recharts';

export default function TrendTab({ trendData }) {
  return (
    <div className="space-y-6">
      {!trendData ? (
        <AnalysisEmptyState
          icon={TrendingUp}
          title="트렌드 데이터를 불러올 수 없습니다"
          subtitle="백엔드 API 연결을 확인하세요"
        />
      ) : (
      <>
      {/* KPI 요약 카드 */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {(trendData.kpis || []).map((kpi, idx) => (
          <div key={idx} className="rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-sf-brown/60">{kpi.name}</span>
              <span className={`flex items-center gap-1 text-xs font-bold ${
                kpi.change >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {kpi.change >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                {kpi.change >= 0 ? '+' : ''}{kpi.change}%
              </span>
            </div>
            <div className="text-2xl font-black text-sf-brown">
              {typeof kpi.current === 'number' ? kpi.current.toLocaleString() : kpi.current}{kpi.name.includes('률') || kpi.name.includes('OEE') || kpi.name.includes('수율') ? '%' : ''}
            </div>
            <div className="text-xs text-sf-brown/50">이전: {kpi.previous != null ? kpi.previous.toLocaleString() : '-'}</div>
          </div>
        ))}
      </div>

      {/* 일별 메트릭 차트 */}
      {(trendData.daily_metrics?.length > 0) && (
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="mb-4 text-sm font-black text-sf-brown">일별 핵심 지표 추이</div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trendData.daily_metrics}>
            <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
            <XAxis dataKey="date" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
            <YAxis yAxisId="left" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="daily_active_equipment" name="일일 가동 설비" stroke="#FF8C42" strokeWidth={2} dot={{ r: 4 }} />
            <Line yAxisId="left" type="monotone" dataKey="new_registrations" name="신규 등록" stroke="#4ADE80" strokeWidth={2} dot={{ r: 4 }} />
            <Line yAxisId="right" type="monotone" dataKey="total_work_orders" name="작업지시 수" stroke="#60A5FA" strokeWidth={2} dot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      )}

      {/* 예측 & 상관관계 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={18} className="text-sf-orange" />
            <span className="text-sm font-black text-sf-brown">생산량 예측 (5일)</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={trendData.forecast || []}>
              <defs>
                <linearGradient id="trend-colorForecast" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#A78BFA" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#A78BFA" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
              <XAxis dataKey="date" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <YAxis tick={{ fill: '#5C4A3D', fontSize: 11 }} domain={['dataMin - 20', 'dataMax + 20']} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="upper" name="상한" stroke="transparent" fill="#A78BFA" fillOpacity={0.2} />
              <Area type="monotone" dataKey="lower" name="하한" stroke="transparent" fill="transparent" />
              <Line type="monotone" dataKey="predicted_active_equipment" name="예측 생산량" stroke="#A78BFA" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={18} className="text-sf-orange" />
            <span className="text-sm font-black text-sf-brown">상관관계 히트맵</span>
          </div>
          {(() => {
            const corrList = trendData.correlation || [];
            if (corrList.length === 0) return <div className="text-sm text-sf-brown/50 text-center py-4">상관관계 데이터가 없습니다</div>;
            // 변수 목록 추출
            const varsSet = new Set();
            corrList.forEach(item => {
              varsSet.add(item.var1 || item.metric1);
              varsSet.add(item.var2 || item.metric2);
            });
            const vars = Array.from(varsSet);
            // 상관계수 맵 생성
            const corrMap = {};
            corrList.forEach(item => {
              const v1 = item.var1 || item.metric1;
              const v2 = item.var2 || item.metric2;
              const c = item.correlation ?? 0;
              corrMap[`${v1}-${v2}`] = c;
              corrMap[`${v2}-${v1}`] = c;
            });
            vars.forEach(v => { corrMap[`${v}-${v}`] = 1.0; });

            function getCellBg(val) {
              if (val >= 0.7) return 'bg-blue-600 text-white';
              if (val >= 0.3) return 'bg-blue-200 text-blue-900';
              if (val >= 0) return 'bg-gray-100 text-gray-600';
              if (val >= -0.3) return 'bg-gray-100 text-gray-600';
              if (val >= -0.7) return 'bg-red-200 text-red-900';
              return 'bg-red-600 text-white';
            }

            return (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr>
                      <th className="p-1"></th>
                      {vars.map(v => <th key={v} className="p-1 font-bold text-sf-brown truncate max-w-[60px]">{v}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {vars.map(row => (
                      <tr key={row}>
                        <td className="p-1 font-bold text-sf-brown truncate max-w-[60px]">{row}</td>
                        {vars.map(col => {
                          const val = corrMap[`${row}-${col}`] ?? 0;
                          return (
                            <td key={col} className={`p-1 text-center rounded font-bold ${getCellBg(val)}`}>
                              {val.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })()}
        </div>
      </div>
      </>
      )}
    </div>
  );
}
