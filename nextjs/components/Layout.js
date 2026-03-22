// Layout.js - 스마트팩토리 AI 플랫폼
import { useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import Topbar from '@/components/Topbar';

export default function Layout({
  auth,
  onLogout,
  children,
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showWelcomePopup, setShowWelcomePopup] = useState(true);

  const username = auth?.username || 'USER';

  // useCallback: Topbar/Sidebar에 전달하는 콜백 안정화 → memo된 자식 리렌더 방지
  const openSidebar = useCallback(() => setSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const closeWelcomePopup = useCallback(() => setShowWelcomePopup(false), []);

  return (
    <div
      className="antialiased min-h-screen bg-gradient-to-br from-sf-yellow/10 via-white to-sf-orange/5"
    >
      {/* 배경 장식 */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-20 left-20 w-40 h-40 bg-sf-yellow/15 rounded-full blur-3xl"></div>
        <div className="absolute bottom-40 right-20 w-60 h-60 bg-sf-orange/10 rounded-full blur-3xl"></div>
        <div className="absolute top-1/2 left-1/3 w-32 h-32 bg-sf-yellow/15 rounded-full blur-2xl"></div>
      </div>

      <Topbar
        username={username}
        onOpenSidebar={openSidebar}
        onLogout={onLogout}
      />

      <div className="relative z-10 mx-auto max-w-[1400px] px-3 sm:px-4">
        <div className="grid grid-cols-12 gap-4 pb-10 pt-3">
          <div className="col-span-12 xl:col-span-3 relative">
            <Sidebar
              auth={auth}
              onLogout={onLogout}
              open={sidebarOpen}
              onClose={closeSidebar}
              showWelcomePopup={showWelcomePopup}
              onCloseWelcomePopup={closeWelcomePopup}
            />
          </div>

          <main className="col-span-12 xl:col-span-9">
            <div className="rounded-[32px] border-2 border-sf-orange/10 bg-white/80 p-4 shadow-lift-lg backdrop-blur-sm md:p-5 animate-fade-in">
              {children}
            </div>
          </main>
        </div>

      </div>
    </div>
  );
}
