import React from 'react';
import { LogOut, Menu } from 'lucide-react';

// React.memo: Layout 내부 상태 변경(sidebarOpen 등) 시 불필요한 리렌더 방지
export default React.memo(function Topbar({ username, onOpenSidebar, onLogout }) {
  return (
    <header className="sticky top-0 z-40">
      <div className="mx-auto max-w-[1320px] px-3 sm:px-4">
        <div className="mt-3 rounded-3xl border-2 border-sf-orange/20 bg-white/80 px-3 py-2 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onOpenSidebar}
                className="inline-flex items-center justify-center rounded-2xl border-2 border-sf-orange/20 bg-white/80 p-2 text-sf-brown shadow-sm hover:bg-sf-yellow/20 active:translate-y-[1px] xl:hidden"
                aria-label="Open menu"
              >
                <Menu size={18} />
              </button>

              <div className="flex items-center gap-2 group cursor-pointer hover:opacity-80 transition-opacity duration-200">
                <div className="h-9 w-9 rounded-2xl bg-white border border-sf-orange/20 shadow-sm flex items-center justify-center overflow-hidden transition-transform duration-300 group-hover:scale-110">
                  <span className="text-lg">🏭</span>
                </div>
                <div>
                  <div className="text-xs font-extrabold tracking-wide sf-text">
                    스마트팩토리 AI 플랫폼
                  </div>
                  <div className="text-[11px] font-semibold text-sf-orange/80">
                    {username}
                  </div>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={onLogout}
              className="inline-flex items-center gap-2 rounded-2xl border-2 border-sf-orange/20 bg-white/80 px-3 py-2 text-xs font-extrabold text-sf-brown shadow-sm hover:bg-sf-yellow/20 hover:scale-105 active:translate-y-[1px] transition-all duration-200"
              data-tooltip="로그아웃"
            >
              <LogOut size={16} />
              로그아웃
            </button>
          </div>
        </div>
      </div>
    </header>
  );
});
