import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { loadFromSession, STORAGE_KEYS } from '@/lib/storage';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const auth = loadFromSession(STORAGE_KEYS.AUTH, null);
    if (auth?.username && auth?.password_b64) router.replace('/app');
    else router.replace('/login');
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );
}
