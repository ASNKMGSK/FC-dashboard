// components/panels/analysis/common/EquipmentSearchInput.js
// 생산라인 검색 + 빠른 선택 공통 컴포넌트

import { Search } from 'lucide-react';

const DEFAULT_QUICK_IDS = ['FM-LINE1', 'FM-LINE2', 'FM-LINE3'];

export default function EquipmentSearchInput({
  value,
  onChange,
  onSearch,
  loading,
  quickSelectIds = DEFAULT_QUICK_IDS,
  placeholder = '라인 ID 입력 (예: FM-LINE1)',
  buttonLabel = '검색',
  loadingLabel = '조회중...',
  inputRef,
}) {
  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') onSearch(); }}
          placeholder={placeholder}
          className="flex-1 rounded-xl border-2 border-sf-orange/20 bg-white px-4 py-2.5 text-sm font-semibold text-sf-brown placeholder:text-sf-brown/40 outline-none focus:border-sf-orange transition-all"
        />
        <button
          onClick={onSearch}
          disabled={loading}
          className="px-5 py-2.5 rounded-xl bg-sf-beige text-sf-brown font-bold text-sm shadow-md hover:shadow-lg transition disabled:opacity-50"
        >
          {loading ? loadingLabel : buttonLabel}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-sf-brown/60">빠른 선택:</span>
        {quickSelectIds.map(id => (
          <button
            key={id}
            onClick={() => { onChange(id); onSearch(id); }}
            className="px-2 py-1 rounded-lg bg-sf-beige text-xs font-semibold text-sf-brown hover:bg-sf-yellow/30 transition"
          >
            {id}
          </button>
        ))}
      </div>
    </div>
  );
}
