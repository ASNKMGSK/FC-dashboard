import React, { useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/cn';

export default React.memo(function Tabs({ tabs = [], active, onChange }) {
  const tabListRef = useRef(null);

  const handleKeyDown = useCallback((e) => {
    const currentIndex = tabs.findIndex(t => t.key === active);
    let nextIndex = -1;

    if (e.key === 'ArrowRight') {
      e.preventDefault();
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = tabs.length - 1;
    }

    if (nextIndex >= 0) {
      onChange(tabs[nextIndex].key);
      const buttons = tabListRef.current?.querySelectorAll('[role="tab"]');
      buttons?.[nextIndex]?.focus();
    }
  }, [tabs, active, onChange]);

  return (
    <div className="mb-4">
      <div
        ref={tabListRef}
        role="tablist"
        aria-label="탭 목록"
        className="flex flex-wrap gap-2 rounded-3xl border-2 border-sf-orange/20 bg-white/80 p-2 shadow-md backdrop-blur"
      >
        {tabs.map((t) => {
          const isActive = t.key === active;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              tabIndex={isActive ? 0 : -1}
              onClick={() => onChange(t.key)}
              onKeyDown={handleKeyDown}
              className={cn(
                'relative rounded-2xl px-4 py-2 text-sm font-black transition-all duration-200 active:scale-[0.97] hover:scale-[1.03] hover:-translate-y-0.5',
                isActive
                  ? 'text-sf-brown shadow-sf-sm'
                  : 'bg-white/70 text-sf-brown/60 hover:bg-sf-yellow/20'
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 rounded-2xl bg-sf-beige shadow-sf-sm"
                  transition={{ type: "spring", damping: 25, stiffness: 300 }}
                />
              )}
              <span className="relative z-10">{t.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
