// 페이지 가시성 공통 훅
// document.hidden 체크를 개별 컴포넌트에서 중복하지 않고, 한 곳에서 관리
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * 페이지 가시성 상태를 반환하는 훅
 * @returns {boolean} isVisible - 탭이 활성 상태인지 여부
 */
export function usePageVisibility() {
  const [isVisible, setIsVisible] = useState(() =>
    typeof document !== 'undefined' ? !document.hidden : true
  );

  useEffect(() => {
    const handler = () => setIsVisible(!document.hidden);
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, []);

  return isVisible;
}

/**
 * 탭 가시성 연동 폴링 훅
 * - 탭 비활성 시 interval을 완전 해제하고, 활성 시 재시작
 * - 에러 시 exponential backoff (기본 최대 30초)
 * - 탭 전환 시 이전 요청 abort
 *
 * @param {Function} fn - 폴링 콜백 (AbortSignal을 인자로 받음)
 * @param {number} intervalMs - 폴링 간격 (ms)
 * @param {Object} [options]
 * @param {boolean} [options.enabled=true] - 폴링 활성화 여부
 * @param {boolean} [options.immediate=false] - 마운트/탭복귀 시 즉시 실행
 * @param {number} [options.maxBackoff=30000] - 최대 백오프 간격 (ms)
 */
export function usePolling(fn, intervalMs, options = {}) {
  const { enabled = true, immediate = false, maxBackoff = 30000 } = options;
  const fnRef = useRef(fn);
  const abortRef = useRef(null);
  const backoffRef = useRef(0); // 연속 실패 횟수

  useEffect(() => { fnRef.current = fn; }, [fn]);

  const isVisible = usePageVisibility();

  // 이전 요청 abort 헬퍼
  const abortPrevious = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled || !isVisible) {
      abortPrevious();
      return;
    }

    const run = async () => {
      abortPrevious();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await fnRef.current(controller.signal);
        backoffRef.current = 0; // 성공 시 백오프 리셋
      } catch (e) {
        if (e?.name !== 'AbortError') {
          backoffRef.current = Math.min(backoffRef.current + 1, 10);
        }
      }
    };

    if (immediate) run();

    const getDelay = () => {
      if (backoffRef.current === 0) return intervalMs;
      // exponential backoff: interval * 2^failures, capped at maxBackoff
      return Math.min(intervalMs * Math.pow(2, backoffRef.current), maxBackoff);
    };

    // 동적 딜레이를 위해 setTimeout 체인 사용
    let timeoutId;
    const schedule = () => {
      timeoutId = setTimeout(async () => {
        await run();
        schedule();
      }, getDelay());
    };
    schedule();

    return () => {
      clearTimeout(timeoutId);
      abortPrevious();
    };
  }, [enabled, isVisible, intervalMs, immediate, maxBackoff, abortPrevious]);
}
