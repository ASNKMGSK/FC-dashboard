// components/panels/analysis/LifecycleTab.js
// 설비 수명주기 분석 탭

import { useState, useMemo } from 'react';
import { Target, Repeat, Activity } from 'lucide-react';
import CustomTooltip from '@/components/common/CustomTooltip';
import AnalysisEmptyState from './common/EmptyState';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

export default function LifecycleTab({ lifecycleData }) {
  const [lifecycleTab, setLifecycleTab] = useState('retention');

  const weekKeys = useMemo(() => {
    if (!lifecycleData?.retention?.length) return ['week0'];
    const allKeys = new Set();
    lifecycleData.retention.forEach(row => {
      Object.keys(row).forEach(k => {
        if (k.startsWith('week')) allKeys.add(k);
      });
    });
    return ['week0', ...Array.from(allKeys).filter(k => k !== 'week0').sort((a, b) => parseInt(a.replace('week', '')) - parseInt(b.replace('week', '')))];
  }, [lifecycleData]);

  return (
    <div className="space-y-6">
      {!lifecycleData ? (
        <AnalysisEmptyState
          icon={Target}
          title="설비 수명주기 데이터를 불러올 수 없습니다"
          subtitle="백엔드 API 연결을 확인하세요"
        />
      ) : (
      <>
      {/* 수명주기 분석 유형 선택 */}
      <div className="flex gap-2">
        {[
          { key: 'retention', label: '가동률 추이', icon: Repeat },
          { key: 'rul', label: '설비 잔존수명', icon: Activity },
          { key: 'production_flow', label: '생산 공정별 처리 현황', icon: Target },
        ].map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setLifecycleTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                lifecycleTab === tab.key
                  ? 'bg-sf-beige text-sf-brown'
                  : 'bg-white border-2 border-sf-orange/20 text-sf-brown hover:bg-sf-beige'
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 가동률 추이 히트맵 */}
      {lifecycleTab === 'retention' && (
        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="mb-4 text-sm font-black text-sf-brown">주간 설비 가동률 추이</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-sf-orange/10">
                  <th className="text-left py-3 px-3 font-bold text-sf-brown">설비 그룹</th>
                  {weekKeys.map(week => (
                    <th key={week} className="text-center py-3 px-3 font-bold text-sf-brown">
                      Week {week.replace('week', '')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(lifecycleData.retention || []).map((row, idx) => (
                  <tr key={idx} className="border-b border-sf-orange/5">
                    <td className="py-3 px-3 font-semibold text-sf-brown">{row.cohort}</td>
                    {weekKeys.map((week) => (
                      <td key={week} className="py-3 px-3 text-center">
                        {row[week] != null ? (
                          <span
                            className="inline-block px-3 py-1 rounded-lg text-xs font-bold"
                            style={{
                              backgroundColor: `rgba(255, 140, 66, ${Number(row[week]) / 100})`,
                              color: Number(row[week]) > 50 ? 'white' : '#5C4A3D'
                            }}
                          >
                            {typeof row[week] === 'number' ? row[week].toFixed(1) : row[week]}%
                          </span>
                        ) : (
                          <span className="text-sf-brown/30">-</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 설비 잔존수명 분석 */}
      {lifecycleTab === 'rul' && (
        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="mb-4 text-sm font-black text-sf-brown">설비 그룹별 잔존수명 (RUL)</div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={lifecycleData.rul_by_cohort || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
              <XAxis dataKey="cohort" tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <YAxis tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="rul" name="잔존수명 (시간)" fill="#FF8C42" radius={[4, 4, 0, 0]} />
              <Bar dataKey="equipment" name="설비 수" fill="#4ADE80" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 생산 공정별 처리 현황 */}
      {lifecycleTab === 'production_flow' && (
        <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
          <div className="mb-4 text-sm font-black text-sf-brown">생산 공정별 처리 현황</div>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={lifecycleData.production_flow || []} margin={{ top: 20, right: 30, left: 0, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#FFD93D40" />
              <XAxis dataKey="step" tick={{ fill: '#5C4A3D', fontSize: 10 }} angle={-15} textAnchor="end" />
              <YAxis tick={{ fill: '#5C4A3D', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="처리 수량" fill="#FF8C42" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      </>
      )}
    </div>
  );
}
