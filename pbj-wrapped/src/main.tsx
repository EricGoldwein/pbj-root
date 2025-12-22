import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App';
import './index.css';

// Determine basename based on current path
// If we're at /sff/, use empty basename, otherwise use /pbj-wrapped
const getBasename = (): string => {
  if (typeof window !== 'undefined') {
    const path = window.location.pathname;
    if (path.startsWith('/sff')) {
      return '';
    }
  }
  return '/pbj-wrapped';
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter
      basename={getBasename()}
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);

