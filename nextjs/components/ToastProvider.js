import { Toaster } from 'react-hot-toast';

export default function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 2600,
        style: {
          background: 'var(--panel2)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: '14px',
          boxShadow: 'var(--shadowHover)',
        },
      }}
    />
  );
}
