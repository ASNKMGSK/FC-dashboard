// pages/app.js - 스마트팩토리 AI 플랫폼
// 제조AI 기반 내부 시스템

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';

import dynamic from 'next/dynamic';

import Layout from '@/components/Layout';
import Tabs from '@/components/Tabs';

const PanelLoader = () => (
  <div className="animate-pulse p-6 space-y-4">
    <div className="h-6 bg-gray-200 rounded w-1/3"></div>
    <div className="h-4 bg-gray-200 rounded w-2/3"></div>
    <div className="h-4 bg-gray-200 rounded w-1/2"></div>
  </div>
);

const DashboardPanel = dynamic(() => import('@/components/panels/DashboardPanel'), { ssr: false, loading: PanelLoader });
const AnalysisPanel = dynamic(() => import('@/components/panels/AnalysisPanel'), { ssr: false, loading: PanelLoader });
const ModelsPanel = dynamic(() => import('@/components/panels/ModelsPanel'), { ssr: false, loading: PanelLoader });
const UsersPanel = dynamic(() => import('@/components/panels/UsersPanel'), { ssr: false, loading: PanelLoader });
const LogsPanel = dynamic(() => import('@/components/panels/LogsPanel'), { ssr: false, loading: PanelLoader });
const StandControlPanel = dynamic(() => import('@/components/panels/StandControlPanel'), { ssr: false, loading: PanelLoader });

import { apiCall as apiCallRaw } from '@/lib/api';
import {
  loadFromStorage,
  saveToStorage,
  loadFromSession,
  removeFromSession,
  STORAGE_KEYS,
} from '@/lib/storage';


const DEFAULT_SETTINGS = {};

function formatTimestamp(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}:${pad(d.getSeconds())}`;
}

export default function AppPage() {
  const router = useRouter();

  const [auth, setAuth] = useState(null);
  const [equipmentList, setEquipmentList] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedEquipment, setSelectedEquipment] = useState(null);

  const [settings, setSettings] = useState(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  const [activityLog, setActivityLog] = useState([]);

  const [activeTab, setActiveTab] = useState('dashboard');

  const isAdmin = auth?.user_role === '관리자';

  const tabs = useMemo(() => {
    if (isAdmin) {
      return [
        { key: 'dashboard', label: '📊 공정 모니터링' },
        { key: 'control', label: '🎛️ 스탠드 제어' },
        { key: 'analysis', label: '📈 품질/SPC' },
        { key: 'models', label: '🧠 AI 모델/MLOps' },
        { key: 'users', label: '👥 사용자 관리' },
        { key: 'logs', label: '📋 로그' },
      ];
    }
    return [
      { key: 'dashboard', label: '📊 공정 모니터링' },
      { key: 'analysis', label: '📈 품질/SPC' },
    ];
  }, [isAdmin]);

  // apiCallRaw는 모듈 스코프 함수이므로 안정 참조 유지
  const apiCall = useCallback((args) => apiCallRaw(args), []);

  const addLog = useCallback(
    (action, detail) => {
      const row = {
        시간: formatTimestamp(new Date()),
        사용자: auth?.username || '-',
        작업: action,
        상세: detail,
      };
      setActivityLog((prev) => [...prev, row]);
    },
    [auth?.username]
  );

  const safeReplace = useCallback(
    (path) => {
      if (!router.isReady) return;
      const cur = router.asPath || '';
      if (cur === path) return;
      router.replace(path);
    },
    [router]
  );

  const onLogout = useCallback(() => {
    removeFromSession(STORAGE_KEYS.AUTH);
    safeReplace('/login');
  }, [safeReplace]);

  const clearLog = useCallback(() => {
    setActivityLog([]);
  }, []);

  // 반응형 zoom: 작은 화면에서 축소, 큰 화면에서 기본
  useEffect(() => {
    function applyZoom() {
      document.documentElement.style.zoom = window.innerWidth < 1280 ? '0.85' : '0.9';
    }
    applyZoom();
    window.addEventListener('resize', applyZoom);
    return () => {
      window.removeEventListener('resize', applyZoom);
      document.documentElement.style.zoom = '1';
    };
  }, []);

  useEffect(() => {
    if (!router.isReady) return;

    const a = loadFromSession(STORAGE_KEYS.AUTH, null);
    if (!a?.username || !a?.password_b64) {
      safeReplace('/login');
      return;
    }
    setAuth(a);

    const savedSettings = loadFromStorage(STORAGE_KEYS.SETTINGS, null);
    const mergedSettings = { ...DEFAULT_SETTINGS, ...(savedSettings || {}) };
    setSettings(mergedSettings);
    setSettingsLoaded(true);

    setActivityLog(loadFromStorage(STORAGE_KEYS.ACTIVITY_LOG, []));
  }, [router.isReady, safeReplace]);

  // 설비/카테고리 데이터 로드
  useEffect(() => {
    if (!auth?.username || !auth?.password_b64) return;

    let mounted = true;

    async function loadEquipment() {
      try {
        const res = await apiCall({ endpoint: '/api/equipment', auth, timeoutMs: 30000 });
        if (!mounted) return;

        const items = res?.equipment || res?.shops;
        if (res?.status === 'success' && Array.isArray(items)) {
          setEquipmentList(items);
          if (!selectedEquipment && items.length > 0) {
            setSelectedEquipment(items[0].id);
          }
        }
      } catch (e) {
        console.error('Failed to load equipment:', e);
      }
    }

    async function loadCategories() {
      try {
        const res = await apiCall({ endpoint: '/api/equipment-types', auth, timeoutMs: 30000 });
        if (!mounted) return;

        if (res?.status === 'success' && Array.isArray(res.categories)) {
          setCategories(res.categories);
        }
      } catch (e) {
        console.error('Failed to load categories:', e);
      }
    }

    loadEquipment();
    loadCategories();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall, auth]);

  // localStorage 저장 통합 debounce (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (settingsLoaded && settings) {
        saveToStorage(STORAGE_KEYS.SETTINGS, settings);
      }
      saveToStorage(STORAGE_KEYS.ACTIVITY_LOG, activityLog);
    }, 300);
    return () => clearTimeout(timer);
  }, [settings, settingsLoaded, activityLog]);


  if (!auth) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-sf-blue/20 via-white to-sf-accent/10 flex items-center justify-center">
        <div className="text-center">
          <div className="relative inline-block">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-sf-blue to-sf-accent shadow-lg flex items-center justify-center animate-bounce">
              <span className="text-3xl font-black text-white">SF</span>
            </div>
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-14 h-3 bg-sf-accent/20 rounded-full blur-sm animate-pulse"></div>
          </div>
          <div className="mt-6 text-sf-dark font-bold text-lg">로딩 중...</div>
          <div className="mt-2 flex justify-center gap-1">
            <span className="w-2 h-2 bg-sf-blue rounded-full animate-bounce [animation-delay:-0.3s]"></span>
            <span className="w-2 h-2 bg-sf-blue rounded-full animate-bounce [animation-delay:-0.15s]"></span>
            <span className="w-2 h-2 bg-sf-blue rounded-full animate-bounce"></span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Layout
      auth={auth}
      onLogout={onLogout}
    >
      <div className="mb-4 animate-slide-up">
        <div className="flex items-center gap-3">
          <span className="text-3xl font-black text-sf-blue">SF</span>
          <div>
            <h1 className="text-2xl font-bold text-sf-dark">SmartFactory AI Platform</h1>
            <p className="text-sm text-sf-dark/70">설비 운영 · ML 예측/탐지/최적화 · 생산 데이터 분석</p>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-sf-accent/15 text-sf-accent">
            SmartFactory
          </span>
        </div>
      </div>

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      <div className="animate-fade-in">
      {activeTab === 'dashboard' ? (
        <DashboardPanel auth={auth} apiCall={apiCall} />
      ) : null}

      {activeTab === 'control' && isAdmin ? <StandControlPanel auth={auth} apiCall={apiCall} /> : null}

      {activeTab === 'analysis' ? <AnalysisPanel auth={auth} apiCall={apiCall} /> : null}

      {activeTab === 'models' && isAdmin ? <ModelsPanel auth={auth} apiCall={apiCall} /> : null}

      {activeTab === 'users' && isAdmin ? <UsersPanel auth={auth} apiCall={apiCall} /> : null}

      {activeTab === 'logs' && isAdmin ? (
        <LogsPanel activityLog={activityLog} clearLog={clearLog} />
      ) : null}


      </div>
    </Layout>
  );
}
