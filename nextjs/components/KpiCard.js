import React from 'react';
import { cn } from '@/lib/cn';

// React.memo: 대시보드에서 4개씩 렌더되는 순수 표시 컴포넌트
export default React.memo(function KpiCard({
  title,
  value,
  subtitle,
  icon = null,
  tone = 'yellow', // yellow | orange | cream | green | blue | pink
  className = '',
}) {
  const toneMap = {
    yellow: 'from-sf-yellow/20 to-sf-orange/10 border-sf-yellow/40',
    orange: 'from-sf-orange/20 to-sf-yellow/10 border-sf-orange/40',
    cream: 'from-sf-cream to-white border-sf-orange/20',
    green: 'from-emerald-50 to-teal-50 border-emerald-200/70',
    blue: 'from-sky-50 to-cyan-50 border-sky-200/70',
    pink: 'from-rose-50 to-pink-50 border-rose-200/70',
  };

  return (
    <div
      className={cn(
        'group rounded-2xl border-2 bg-gradient-to-br p-3 shadow-[0_10px_30px_-18px_rgba(110,76,30,0.25)] backdrop-blur',
        'transition-all duration-300 hover:scale-[1.03] hover:shadow-xl hover:-translate-y-1',
        toneMap[tone] || toneMap.yellow,
        className
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-extrabold tracking-wide text-sf-brown/70 leading-tight">{title}</div>
          <div className="mt-0.5 text-xs font-black tabular-nums text-sf-brown leading-tight">{value}</div>
          {subtitle ? <div className="mt-0.5 text-[10px] font-semibold text-sf-brown/60 leading-tight">{subtitle}</div> : null}
        </div>

        {icon ? (
          <div className="shrink-0 rounded-xl border border-sf-orange/20 bg-white/70 p-1.5 shadow-sm group-hover:scale-110 group-hover:rotate-3 transition-transform duration-300">
            {icon}
          </div>
        ) : null}
      </div>
    </div>
  );
});
