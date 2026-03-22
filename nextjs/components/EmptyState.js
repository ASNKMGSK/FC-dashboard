import React from 'react';
import { Factory } from 'lucide-react';

// React.memo: 여러 패널에서 사용하는 순수 표시 컴포넌트
export default React.memo(function EmptyState({ icon: Icon, title = '데이터가 없습니다', desc = '조건을 바꿔 다시 시도해보세요.' }) {
  const IconComponent = Icon || Factory;
  return (
    <div className="rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-6 shadow-sm backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl border-2 border-sf-orange/20 bg-gradient-to-br from-sf-yellow/30 via-sf-orange/20 to-sf-yellow/30 p-3 shadow-sm">
          <IconComponent className="text-sf-brown" size={18} />
        </div>
        <div>
          <div className="text-sm font-black text-sf-brown">{title}</div>
          <div className="text-xs font-semibold text-sf-brown/60">{desc}</div>
        </div>
      </div>
    </div>
  );
});
