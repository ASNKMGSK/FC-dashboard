// components/common/StatCard.js
// 통합 통계 카드

const COLOR_MAP = {
  indigo: 'border-indigo-200 bg-indigo-50/50 text-indigo-600',
  red: 'border-red-200 bg-red-50/50 text-red-600',
  amber: 'border-amber-200 bg-amber-50/50 text-amber-600',
  emerald: 'border-emerald-200 bg-emerald-50/50 text-emerald-600',
  teal: 'border-teal-200 bg-teal-50/50 text-teal-600',
  blue: 'border-blue-200 bg-blue-50/50 text-blue-600',
};

export default function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className={`rounded-2xl border p-4 ${COLOR_MAP[color] || COLOR_MAP.indigo}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={16} />
        <span className="text-xs font-medium text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold">{value}</p>
    </div>
  );
}
