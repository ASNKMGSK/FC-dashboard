export const STORAGE_KEYS = {
  AUTH: 'sf_auth',
  SETTINGS: 'sf_settings',
  ACTIVITY_LOG: 'sf_activity_log',
  TOTAL_QUERIES: 'sf_total_queries',
};

export function safeJsonParse(value, fallback) {
  try {
    if (!value) return fallback;
    return JSON.parse(value);
  } catch (e) {
    return fallback;
  }
}

export function loadFromStorage(key, fallback) {
  if (typeof window === 'undefined') return fallback;
  return safeJsonParse(window.localStorage.getItem(key), fallback);
}

// localStorage 저장 크기 제한 (1MB)
const MAX_STORAGE_BYTES = 1 * 1024 * 1024;

export function saveToStorage(key, value) {
  if (typeof window === 'undefined') return;
  try {
    const serialized = JSON.stringify(value);
    // 크기 제한 초과 시 저장하지 않음
    if (serialized.length > MAX_STORAGE_BYTES) {
      console.warn(`[storage] "${key}" 크기 초과 (${(serialized.length / 1024).toFixed(1)}KB > ${MAX_STORAGE_BYTES / 1024}KB), 저장 건너뜀`);
      return;
    }
    window.localStorage.setItem(key, serialized);
  } catch (e) {
    // QuotaExceededError 등 localStorage 오류 처리
    console.warn(`[storage] "${key}" 저장 실패:`, e?.message || e);
  }
}

export function removeFromStorage(key) {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(key);
}

export function loadFromSession(key, fallback) {
  if (typeof window === 'undefined') return fallback;
  return safeJsonParse(window.sessionStorage.getItem(key), fallback);
}

export function saveToSession(key, value) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(key, JSON.stringify(value));
}

export function removeFromSession(key) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(key);
}
