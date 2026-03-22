import React from 'react';

// React.memo: 거의 모든 패널에서 사용하는 순수 표시 컴포넌트
export default React.memo(function SectionHeader({ title, subtitle, right }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-black text-sf-brown">{title}</h2>
        {subtitle ? <p className="text-xs font-semibold text-sf-brown/60">{subtitle}</p> : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
});
