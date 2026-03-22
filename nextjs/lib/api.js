// GET 요청용 인메모리 캐시 (TTL 60초, 정적 데이터 전용)
const _apiCache = new Map();
const CACHE_TTL = 60_000;
const CACHE_MAX_SIZE = 50; // 캐시 무한 증가 방지

// 동일 요청 중복 호출 방지 (in-flight 요청 공유)
const _inflightRequests = new Map();

// 캐시 대상 엔드포인트 (정적 데이터만)
const CACHEABLE_ENDPOINTS = ['/api/equipment', '/api/equipment-types'];

function _getCacheKey(endpoint, auth) {
  return `${endpoint}::${auth?.username || ''}`;
}

function _getCached(key) {
  const entry = _apiCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL) {
    _apiCache.delete(key);
    return null;
  }
  return entry.data;
}

function _setCache(key, data) {
  // 캐시 크기 제한: 오래된 항목부터 제거
  if (_apiCache.size >= CACHE_MAX_SIZE) {
    const firstKey = _apiCache.keys().next().value;
    _apiCache.delete(firstKey);
  }
  _apiCache.set(key, { data, ts: Date.now() });
}

export function getApiBase() {
  // ✅ 중요: 외부 접속에서도 동작하게 기본값을 '같은 오리진'으로 둠
  // - 로컬 개발에서 백엔드가 다른 호스트/포트면 NEXT_PUBLIC_API_BASE를 지정
  //   예) NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
  const base = process.env.NEXT_PUBLIC_API_BASE || '';
  return String(base).replace(/\/$/, '');
}

/**
 * Basic Auth 헤더 생성
 * @param {string} username
 * @param {string} passwordOrB64 - 평문 비밀번호 또는 btoa 인코딩된 비밀번호
 * @param {boolean} [isB64=false] - true면 passwordOrB64를 atob으로 디코딩 후 사용
 */
export function makeBasicAuthHeader(username, passwordOrB64, isB64 = false) {
  if (typeof window === 'undefined') return '';
  const password = isB64 ? window.atob(passwordOrB64) : passwordOrB64;
  const token = window.btoa(`${username}:${password}`);
  return `Basic ${token}`;
}

export async function apiCall({
  endpoint,
  method = 'GET',
  data = null,
  auth = null,
  timeoutMs = 60000,
  headers = {},
  responseType = 'json',
  cache = 'no-store',
}) {
  const isGet = method === 'GET';
  const isCacheable = isGet && CACHEABLE_ENDPOINTS.includes(endpoint);
  const requestKey = isGet ? _getCacheKey(endpoint, auth) : null;

  // GET 캐시 히트 확인 (정적 데이터 엔드포인트만)
  if (isCacheable) {
    const cached = _getCached(requestKey);
    if (cached) return cached;
  }

  // 모든 GET 요청: 동일 요청이 이미 진행 중이면 결과 공유 (폴링 중복 호출 방지)
  if (isGet) {
    const inflight = _inflightRequests.get(requestKey);
    if (inflight) return inflight;
  }

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);

  const base = getApiBase();
  const url = `${base}${endpoint}`;

  const init = {
    method,
    cache,
    signal: controller.signal,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  };

  if (auth?.username && (auth?.password || auth?.password_b64)) {
    const pw = auth.password_b64 || auth.password;
    const isB64 = !!auth.password_b64;
    init.headers['Authorization'] = makeBasicAuthHeader(auth.username, pw, isB64);
  }

  if (method !== 'GET' && method !== 'HEAD' && data !== null) {
    init.body = JSON.stringify(data);
  }

  const doFetch = async () => {
    try {
      const resp = await fetch(url, init);
      clearTimeout(t);

      if (responseType === 'blob') {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.blob();
      }

      const json = await resp.json().catch(() => ({}));

      // 성공한 GET 정적 데이터 캐시 저장
      if (isCacheable && json?.status === 'success') {
        _setCache(requestKey, json);
      }

      return json;
    } catch (e) {
      clearTimeout(t);
      // AbortController 타임아웃 에러 구분
      if (e?.name === 'AbortError') {
        return { status: 'error', message: '요청 시간 초과' };
      }
      return { status: 'error', message: String(e?.message || e) };
    }
  };

  // 모든 GET 요청: in-flight 공유로 동일 URL 중복 호출 방지
  if (isGet && requestKey) {
    const promise = doFetch().finally(() => _inflightRequests.delete(requestKey));
    _inflightRequests.set(requestKey, promise);
    return promise;
  }

  return doFetch();
}
