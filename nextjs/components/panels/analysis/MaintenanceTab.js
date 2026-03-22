// components/panels/analysis/MaintenanceTab.js
// 정비 분석 탭

import { Wrench, MessageSquare } from 'lucide-react';
import AnalysisEmptyState from './common/EmptyState';

export default function MaintenanceTab({ csData }) {
  return (
    <div className="space-y-6">
      {!csData ? (
        <AnalysisEmptyState
          icon={MessageSquare}
          title="정비 데이터를 불러올 수 없습니다"
          subtitle="백엔드 API 연결을 확인하세요"
        />
      ) : (
      <>
      {/* 유형별 정비 현황 */}
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={18} className="text-sf-orange" />
          <span className="text-sm font-black text-sf-brown">유형별 정비 현황</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b-2 border-sf-orange/10">
                <th className="text-left py-3 px-2 font-bold text-sf-brown">정비 유형</th>
                <th className="text-right py-3 px-2 font-bold text-sf-brown">요청 수</th>
                <th className="text-right py-3 px-2 font-bold text-sf-brown">평균 품질</th>
                <th className="text-right py-3 px-2 font-bold text-sf-brown">대기중</th>
                <th className="text-left py-3 px-2 font-bold text-sf-brown">품질 바</th>
              </tr>
            </thead>
            <tbody>
              {csData.channels.map(ch => (
                <tr key={ch.channel} className="border-b border-sf-orange/5 hover:bg-sf-beige/30 transition">
                  <td className="py-3 px-2 font-semibold text-sf-brown">{ch.channel}</td>
                  <td className="py-3 px-2 text-right text-sf-brown/80">{ch.count.toLocaleString()}</td>
                  <td className="py-3 px-2 text-right">
                    <span className={`font-bold ${parseFloat(ch.quality) >= 90 ? 'text-green-600' : 'text-yellow-600'}`}>
                      {ch.quality}%
                    </span>
                  </td>
                  <td className="py-3 px-2 text-right text-sf-brown/80">{ch.pending}</td>
                  <td className="py-3 px-2 w-40">
                    <div className="h-2 bg-sf-beige rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-sf-yellow to-sf-orange"
                        style={{ width: `${ch.quality}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 최근 정비 샘플 */}
      {csData.recent && csData.recent.length > 0 && (
      <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-5 shadow-sm backdrop-blur">
        <div className="mb-4 text-sm font-black text-sf-brown">최근 정비 샘플</div>
        <div className="space-y-3">
          {csData.recent.map((item, idx) => (
            <div key={idx} className="p-4 rounded-2xl bg-sf-beige/30">
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded-full bg-sf-orange/20 text-xs font-bold text-sf-brown">
                  {item.channel}
                </span>
                <span className={`text-sm font-bold ${item.quality >= 95 ? 'text-green-600' : 'text-yellow-600'}`}>
                  품질 {item.quality}%
                </span>
              </div>
              <p className="text-sm text-sf-brown">&ldquo;{item.text}&rdquo;</p>
            </div>
          ))}
        </div>
      </div>
      )}
      </>
      )}
    </div>
  );
}
