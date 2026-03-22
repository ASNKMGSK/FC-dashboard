// components/panels/analysis/common/EmptyState.js
// 분석 탭 공통 "데이터 없음" 컴포넌트

export default function AnalysisEmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div className="text-center py-16 rounded-3xl border-2 border-sf-orange/20 bg-white/80">
      <Icon size={48} className="mx-auto mb-3 text-sf-brown/30" />
      <p className="text-sm font-semibold text-sf-brown/50">{title}</p>
      {subtitle && <p className="text-xs text-sf-brown/40 mt-1">{subtitle}</p>}
    </div>
  );
}
