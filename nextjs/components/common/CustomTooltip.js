// components/common/CustomTooltip.js
// 공통 Recharts 커스텀 툴팁

export default function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border-2 border-sf-orange/20 bg-white/95 px-3 py-2 shadow-lg backdrop-blur">
      <p className="text-xs font-bold text-sf-brown">{label}</p>
      {payload.map((entry, idx) => (
        <p key={idx} className="text-sm font-semibold" style={{ color: entry.color || entry.fill }}>
          {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
        </p>
      ))}
    </div>
  );
}
