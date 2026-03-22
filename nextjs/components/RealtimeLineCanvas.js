// components/RealtimeLineCanvas.js
// 시간 기반 x축 + 연속 스크롤 실시간 차트 (성능 최적화 버전)
// 최적화: RAF 통합 루프, GC pressure 감소, gradient 캐싱, binary search viewport culling
import { useRef, useEffect, useCallback } from 'react';

// --- drawSpline: 길이 파라미터로 버퍼 재사용 지원 ---
function drawSpline(ctx, points, len) {
  if (len < 2) return;
  ctx.moveTo(points[0].x, points[0].y);
  if (len === 2) { ctx.lineTo(points[1].x, points[1].y); return; }
  const t = 0.25;
  for (let i = 0; i < len - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(len - 1, i + 2)];
    ctx.bezierCurveTo(
      p1.x + (p2.x - p0.x) * t, p1.y + (p2.y - p0.y) * t,
      p2.x - (p3.x - p1.x) * t, p2.y - (p3.y - p1.y) * t,
      p2.x, p2.y
    );
  }
}

// --- binary search: 정렬된 배열에서 >= target인 첫 인덱스 ---
function lowerBound(arr, target, key) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if ((key ? arr[mid][key] : arr[mid]) < target) lo = mid + 1; else hi = mid;
  }
  return lo;
}

// --- loop-based min/max (spread 방지, stack overflow 안전) ---
function minMaxValues(arr, startIdx, endIdx, key) {
  let mn = Infinity, mx = -Infinity;
  for (let i = startIdx; i < endIdx; i++) {
    const v = key ? arr[i][key] : arr[i].v;
    if (v < mn) mn = v;
    if (v > mx) mx = v;
  }
  return { mn, mx };
}

// --- 통합 RAF 코디네이터: 9개 캔버스를 하나의 루프로 ---
const rafCallbacks = new Set();
let rafId = null;

function rafLoop() {
  rafCallbacks.forEach(cb => cb());
  if (rafCallbacks.size > 0) {
    rafId = requestAnimationFrame(rafLoop);
  } else {
    rafId = null;
  }
}

function registerRaf(cb) {
  rafCallbacks.add(cb);
  if (rafId === null) {
    rafId = requestAnimationFrame(rafLoop);
  }
}

function unregisterRaf(cb) {
  rafCallbacks.delete(cb);
  if (rafCallbacks.size === 0 && rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

// --- gradient 캐시 (color별 1회 생성) ---
const gradientCache = new Map();

function getCachedGradient(ctx, height, color) {
  const cacheKey = color + '|' + height;
  let grad = gradientCache.get(cacheKey);
  if (!grad) {
    grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, color + '18');
    grad.addColorStop(1, color + '00');
    gradientCache.set(cacheKey, grad);
  }
  return grad;
}

/**
 * 미니 스파크라인 (3x3 전류 그리드) - 성능 최적화
 * data: [{ t: timestamp(ms), v: number }, ...]
 * 시간 기반 x축으로 viewport가 자연스럽게 흘러감
 */
export default function RealtimeLineCanvas({
  data = [],
  color = '#059669',
  width = 200,
  height = 50,
  lineWidth = 1.5,
  windowMs = 20000,
}) {
  const canvasRef = useRef(null);
  const dataRef = useRef(data);
  // 재사용 가능한 포인트 버퍼
  const pointBuf = useRef([]);
  // dirty flag: 데이터 변경 감지
  const lastDataLen = useRef(0);
  const lastDataRef = useRef(null);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    // DPR 설정 - 마운트 시 1회만
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const pad = 3, cw = width - pad * 2, ch = height - pad * 2;
    const padCh = pad + ch; // 사전 계산

    const draw = () => {
      const pts = dataRef.current;
      if (!pts || pts.length < 2) return;

      // 시간 기반 viewport (Date.now 방식 유지)
      const viewEnd = Date.now();
      const viewStart = viewEnd - windowMs;

      // binary search로 viewport 시작점 찾기 (O(log n))
      const startIdx = lowerBound(pts, viewStart, 't');
      const totalLen = pts.length;
      if (totalLen - startIdx < 2) return;

      // min/max: loop 기반 (spread 방지)
      const { mn, mx } = minMaxValues(pts, startIdx, totalLen, null);
      // 마지막 데이터 값 (가상 포인트 연장용)
      const lastPt = pts[totalLen - 1];
      const extendVirtual = viewEnd - lastPt.t > 10;

      // 최소 범위 보장: 평균값의 5% 이상 (스케일 점프 방지)
      const mean = (mn + mx) / 2;
      const minRange = Math.max(mx - mn, Math.abs(mean) * 0.05, 1);
      const yMin = mean - minRange * 0.6, yRng = minRange * 1.2;
      const invWindowMs = 1 / windowMs;
      const invYRng = 1 / yRng;

      // 포인트 버퍼 재사용 (GC pressure 감소)
      const buf = pointBuf.current;
      let bufLen = 0;
      for (let i = startIdx; i < totalLen; i++) {
        const p = pts[i];
        if (bufLen >= buf.length) {
          buf.push({ x: 0, y: 0 });
        }
        buf[bufLen].x = pad + ((p.t - viewStart) * invWindowMs) * cw;
        buf[bufLen].y = padCh - ((p.v - yMin) * invYRng) * ch;
        bufLen++;
      }

      // 가상 포인트 연장 (마지막 데이터 → 현재 시각)
      if (extendVirtual) {
        if (bufLen >= buf.length) buf.push({ x: 0, y: 0 });
        buf[bufLen].x = pad + ((viewEnd - viewStart) * invWindowMs) * cw;
        buf[bufLen].y = padCh - ((lastPt.v - yMin) * invYRng) * ch;
        bufLen++;
      }

      if (bufLen < 2) return;

      ctx.clearRect(0, 0, width, height);

      // fill (gradient 캐싱)
      const grad = getCachedGradient(ctx, height, color);
      ctx.beginPath();
      drawSpline(ctx, buf, bufLen);
      ctx.lineTo(buf[bufLen - 1].x, padCh);
      ctx.lineTo(buf[0].x, padCh);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // stroke
      ctx.beginPath();
      drawSpline(ctx, buf, bufLen);
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.stroke();

      // dot (마지막 점)
      const last = buf[bufLen - 1];
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.25;
      ctx.beginPath();
      ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(last.x, last.y, 1.5, 0, Math.PI * 2);
      ctx.fill();
    };

    // 통합 RAF 루프에 등록
    registerRaf(draw);
    return () => unregisterRaf(draw);
  }, [width, height, color, lineWidth, windowMs]);

  return <canvas ref={canvasRef} style={{ width, height, display: 'block' }} />;
}

/**
 * 멀티라인 Canvas (상세 패널 전류/속도/Setpoint) - 성능 최적화
 * data: [{ _t: timestamp(ms), time: "HH:MM:SS", current, speed, setpoint }, ...]
 */
export function RealtimeMultiLineCanvas({
  data = [],
  lines = [],
  width = 400,
  height = 150,
  showGrid = true,
  showXLabels = true,
  windowMs = 20000,
}) {
  const canvasRef = useRef(null);
  const dataRef = useRef(data);
  // 라인별 재사용 포인트 버퍼
  const lineBufs = useRef({});

  useEffect(() => { dataRef.current = data; }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    // DPR 설정 - 마운트 시 1회만
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const pL = 45, pR = 45, pT = 8, pB = showXLabels ? 22 : 8;
    const cW = width - pL - pR, cH = height - pT - pB;
    const pTcH = pT + cH; // 사전 계산
    const invWindowMs = 1 / windowMs;

    // 라인별 min/max 캐시 (Y축 레이블 재사용)
    const lineMinMax = {};

    const draw = () => {
      const allData = dataRef.current;
      if (!allData || allData.length < 2) return;

      const viewEnd = Date.now();
      const viewStart = viewEnd - windowMs;

      // binary search로 viewport 시작 (data._t 기준)
      const startIdx = lowerBound(allData, viewStart, '_t');
      const totalLen = allData.length;
      if (totalLen - startIdx < 2) return;

      // 가상 포인트 연장 여부
      const lastD = allData[totalLen - 1];
      const extendVirtual = lastD._t && viewEnd - lastD._t > 10;

      ctx.clearRect(0, 0, width, height);

      // grid
      if (showGrid) {
        ctx.strokeStyle = 'rgba(0,0,0,0.06)';
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
          const y = pT + (cH / 4) * i;
          ctx.beginPath(); ctx.moveTo(pL, y); ctx.lineTo(width - pR, y); ctx.stroke();
        }
      }

      // 클리핑
      ctx.save();
      ctx.beginPath();
      ctx.rect(pL, 0, cW, height - pB);
      ctx.clip();

      // 각 라인 그리기
      for (let li = 0; li < lines.length; li++) {
        const { dataKey, color, strokeWidth = 2, dashed = false } = lines[li];

        // loop 기반 min/max + 포인트 변환 (한번의 순회로 처리)
        let mn = Infinity, mx = -Infinity;
        // 버퍼 초기화
        if (!lineBufs.current[dataKey]) lineBufs.current[dataKey] = [];
        const buf = lineBufs.current[dataKey];
        let bufLen = 0;

        for (let i = startIdx; i < totalLen; i++) {
          const d = allData[i];
          const v = d[dataKey];
          if (v == null) continue;
          if (v < mn) mn = v;
          if (v > mx) mx = v;
          if (bufLen >= buf.length) buf.push({ x: 0, y: 0, v: 0, t: 0 });
          buf[bufLen].v = v;
          buf[bufLen].t = d._t || 0;
          bufLen++;
        }

        if (bufLen < 2) continue;

        // 최소 범위 보장: 평균값의 5% 이상 (스케일 점프 방지)
        const lineMean = (mn + mx) / 2;
        const lineMinRange = Math.max(mx - mn, Math.abs(lineMean) * 0.05, 1);
        const yMin = lineMean - lineMinRange * 0.55, yMax = lineMean + lineMinRange * 0.55, yRng = yMax - yMin;
        const invYRng = 1 / yRng;

        // 저장해두고 Y축 레이블에서 재사용
        lineMinMax[dataKey] = { yMin, yMax };

        // x, y 좌표 계산
        for (let i = 0; i < bufLen; i++) {
          buf[i].x = pL + ((buf[i].t - viewStart) * invWindowMs) * cW;
          buf[i].y = pTcH - ((buf[i].v - yMin) * invYRng) * cH;
        }

        // 가상 포인트 연장
        if (extendVirtual) {
          const lastBuf = buf[bufLen - 1];
          if (bufLen >= buf.length) buf.push({ x: 0, y: 0, v: 0, t: 0 });
          buf[bufLen].x = pL + ((viewEnd - viewStart) * invWindowMs) * cW;
          buf[bufLen].y = lastBuf.y;
          bufLen++;
        }

        if (dashed) ctx.setLineDash([4, 2]); else ctx.setLineDash([]);
        ctx.strokeStyle = color;
        ctx.lineWidth = strokeWidth;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.beginPath();
        drawSpline(ctx, buf, bufLen);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      ctx.restore();

      // Y축 레이블 (캐시된 min/max 재사용 - 두번째 순회 제거)
      for (let li = 0; li < lines.length; li++) {
        const { dataKey, color, yAxisSide = 'left' } = lines[li];
        const mm = lineMinMax[dataKey];
        if (!mm) continue;
        ctx.fillStyle = color;
        ctx.font = '9px sans-serif';
        ctx.textAlign = yAxisSide === 'left' ? 'right' : 'left';
        const lx = yAxisSide === 'left' ? pL - 4 : width - pR + 4;
        ctx.fillText(mm.yMax.toFixed(1), lx, pT + 8);
        ctx.fillText(mm.yMin.toFixed(1), lx, pTcH - 2);
      }

      // X축 시간 레이블
      if (showXLabels) {
        ctx.fillStyle = '#999';
        ctx.font = '8px sans-serif';
        ctx.textAlign = 'center';
        const step = windowMs / 5;
        const xStep = cW / 5;
        for (let i = 0; i < 6; i++) {
          const t = viewStart + step * i;
          const x = pL + xStep * i;
          const d = new Date(t);
          const label = `${d.getMinutes()}:${d.getSeconds().toString().padStart(2, '0')}`;
          ctx.fillText(label, x, height - 4);
        }
      }
    };

    // 통합 RAF 루프에 등록
    registerRaf(draw);
    return () => unregisterRaf(draw);
  }, [width, height, lines, showGrid, showXLabels, windowMs]);

  return <canvas ref={canvasRef} style={{ width, height, display: 'block' }} />;
}
