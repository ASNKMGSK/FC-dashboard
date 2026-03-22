// components/common/constants.js
// 공통 차트 색상 상수

// 스마트팩토리 대시보드 테마 색상
export const DASHBOARD_COLORS = {
  primary: ['#1B6FF0', '#42A5F5', '#4ADE80', '#60A5FA', '#F472B6', '#A78BFA'],
  tiers: {
    Basic: '#9CA3AF',
    Standard: '#42A5F5',
    Premium: '#F59E0B',
    Enterprise: '#1B6FF0',
  },
};

// 이상탐지 severity별 CSS 클래스 (AnomalyTab, PredictionTab 공통)
export function getSeverityClasses(severity) {
  switch (severity) {
    case 'high':
      return { border: 'border-red-200', bg: 'bg-red-50', badge: 'bg-red-200 text-red-700', icon: 'bg-red-500' };
    case 'medium':
      return { border: 'border-orange-200', bg: 'bg-orange-50', badge: 'bg-orange-200 text-orange-700', icon: 'bg-orange-500' };
    case 'low':
    default:
      return { border: 'border-yellow-200', bg: 'bg-yellow-50', badge: 'bg-yellow-200 text-yellow-700', icon: 'bg-yellow-500' };
  }
}
