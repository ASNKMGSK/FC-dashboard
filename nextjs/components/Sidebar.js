// components/Sidebar.js
// 스마트팩토리 AI 플랫폼 사이드바
import { useState, useEffect } from 'react';
import { usePageVisibility } from '@/components/panels/hooks/usePageVisibility';
import {
  LogOut,
  Users,
  BarChart3,
  Search,
  Wrench,
  Building2,
  X
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

function SystemStatus() {
  const [healthy, setHealthy] = useState(null);
  const isVisible = usePageVisibility();

  useEffect(() => {
    if (!isVisible) return;
    let mounted = true;
    async function check() {
      try {
        const res = await fetch('/api/health', { signal: AbortSignal.timeout(5000) });
        if (mounted) setHealthy(res.ok);
      } catch {
        if (mounted) setHealthy(false);
      }
    }
    check();
    const id = setInterval(check, 30000);
    return () => { mounted = false; clearInterval(id); };
  }, [isVisible]);

  return (
    <div className="flex items-center justify-center gap-2 mb-2">
      <span className={`w-2.5 h-2.5 rounded-full ${healthy === null ? 'bg-gray-300 animate-pulse' : healthy ? 'bg-emerald-500' : 'bg-red-500'}`} />
      <span className="text-xs text-sf-brown/60">
        {healthy === null ? '확인 중...' : healthy ? '시스템 정상' : '연결 오류'}
      </span>
    </div>
  );
}

function SidebarContent({
  auth,
  onLogout,
  onClose,
  isMobile,
}) {
  return (
    <div className={isMobile ? 'h-full overflow-auto px-4 py-5' : 'px-4 py-5 pb-8'}>
      {/* 모바일 닫기 버튼 */}
      {isMobile && (
        <div className="flex justify-end mb-2">
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-sf-orange/10 transition-colors"
          >
            <X className="w-5 h-5 text-sf-brown" />
          </button>
        </div>
      )}

      {/* 로고 영역 */}
      <div className="pb-4 mb-4 border-b border-sf-orange/20">
        <div className="flex items-start justify-between gap-2">
          <div className="inline-flex items-center gap-3">
            <div className="h-12 w-12 rounded-2xl bg-white border border-sf-orange/20 shadow-sm flex items-center justify-center overflow-hidden">
              <span className="text-2xl">🏭</span>
            </div>
            <div>
              <h2 className="text-base font-black text-sf-brown leading-tight">Smart Factory AI</h2>
              <p className="text-xs font-semibold text-sf-orange">Manufacturing Platform</p>
            </div>
          </div>
        </div>
      </div>

      {/* 기능 소개 배지 */}
      <div className="mb-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-sf-yellow/30 text-sf-brown text-xs font-medium">
          <Wrench className="w-3 h-3" /> 설비
        </span>
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-sf-orange/20 text-sf-orange text-xs font-medium">
          <Search className="w-3 h-3" /> 분석
        </span>
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">
          <BarChart3 className="w-3 h-3" /> 정비
        </span>
      </div>

      {/* 사용자 정보 */}
      {auth?.username && (
        <div className="mb-4 p-3 rounded-xl bg-gradient-to-r from-sf-yellow/20 to-sf-orange/10 border border-sf-orange/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sf-yellow to-sf-orange flex items-center justify-center">
                <Users className="w-4 h-4 text-white" />
              </div>
              <div>
                <p className="text-sm font-bold text-sf-brown">{auth.user_name || auth.username}</p>
                <p className="text-xs text-sf-orange">{auth.user_role || '사용자'}</p>
              </div>
            </div>
            <button
              onClick={onLogout}
              className="p-2 rounded-lg hover:bg-sf-orange/10 transition-colors"
              data-tooltip="로그아웃"
            >
              <LogOut className="w-4 h-4 text-sf-brown/60" />
            </button>
          </div>
        </div>
      )}

      {/* 플랫폼 기능 안내 */}
      <div className="space-y-2 mb-4">
        <h3 className="text-sm font-bold text-sf-brown">주요 기능</h3>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-50/50 border border-blue-100">
            <span className="text-sm">📊</span>
            <span className="text-xs text-sf-brown/80 font-medium">공정 모니터링 — OEE, MTBF/MTTR, 설비 상태</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50/50 border border-emerald-100">
            <span className="text-sm">📈</span>
            <span className="text-xs text-sf-brown/80 font-medium">품질/SPC — X-bar 관리도, Cpk, 이상탐지</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-purple-50/50 border border-purple-100">
            <span className="text-sm">🤖</span>
            <span className="text-xs text-sf-brown/80 font-medium">AI 모델/MLOps — 드리프트 감시, 모델 관리</span>
          </div>
        </div>
      </div>

      {/* 하단 정보 + 시스템 상태 */}
      <div className="mt-6 pt-4 border-t border-sf-orange/20">
        <SystemStatus />
        <div className="text-center mt-3">
          <div className="flex items-center justify-center gap-2">
            <Building2 className="w-4 h-4 text-sf-orange" />
            <span className="text-sm font-bold bg-gradient-to-r from-sf-orange to-sf-yellow bg-clip-text text-transparent">
              Smart Factory AI Platform
            </span>
          </div>
          <p className="text-xs text-sf-brown/40 mt-1">v2.0</p>
        </div>
      </div>
    </div>
  );
}

export default function Sidebar({
  auth,
  onLogout,
  open,
  onClose,
  showWelcomePopup,
  onCloseWelcomePopup,
}) {
  return (
    <>
      {/* 로그인 환영 팝업 */}
      <AnimatePresence>
        {showWelcomePopup && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="hidden xl:block absolute top-24 left-0 z-50 px-3 w-full"
          >
            <div className="bg-white rounded-2xl shadow-2xl p-4 border-2 border-sf-orange/20">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sf-yellow to-sf-orange flex items-center justify-center">
                    <span className="text-xl">🏭</span>
                  </div>
                  <div>
                    <h3 className="text-sm font-black text-sf-brown">환영합니다!</h3>
                    <p className="text-xs text-sf-orange">{auth?.user_name || auth?.username}님</p>
                  </div>
                </div>
                <button
                  onClick={onCloseWelcomePopup}
                  className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <X className="w-4 h-4 text-gray-400" />
                </button>
              </div>

              <p className="text-xs text-sf-brown/70 mb-3">
                스마트팩토리 AI 플랫폼에서 설비 상태, 품질 분석, AI 모델 관리를 한눈에 확인하세요.
              </p>

              <button
                onClick={onCloseWelcomePopup}
                className="w-full py-2 rounded-xl bg-sf-beige text-sf-brown text-sm font-bold shadow-md hover:shadow-lg transition-all"
              >
                시작하기
              </button>
            </div>
            <div className="absolute -bottom-2 left-8 w-4 h-4 bg-white border-r-2 border-b-2 border-sf-orange/20 rotate-45" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* 데스크탑 사이드바 */}
      <aside className="hidden xl:block sticky top-20 max-h-[calc(100vh-6rem)] rounded-[32px] border-2 border-sf-orange/10 bg-white/80 backdrop-blur-sm shadow-lg overflow-y-auto overscroll-contain">
        <SidebarContent
          auth={auth}
          onLogout={onLogout}
          isMobile={false}
        />
      </aside>

      {/* 모바일 사이드바 */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
              className="fixed inset-0 bg-black/30 z-40 xl:hidden"
            />
            <motion.aside
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed left-0 top-0 bottom-0 w-80 bg-gradient-to-b from-sf-yellow/10 via-white to-sf-orange/10 backdrop-blur-md z-50 xl:hidden shadow-2xl overflow-auto"
            >
              <SidebarContent
                auth={auth}
                onLogout={onLogout}
                onClose={onClose}
                isMobile={true}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
