import { Routes, Route, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Index from './pages/Index';
import Wrapped from './pages/wrapped';
import WrappedNews from './pages/wrapped-news';
import SFFWrapped from './pages/sff-wrapped';
import SFFPage from './pages/sff-page';
import { PasswordProtection } from './components/PasswordProtection';

// Declare gtag function for TypeScript
declare global {
  interface Window {
    gtag: (...args: any[]) => void;
    dataLayer: any[];
  }
}

function App() {
  const location = useLocation();

  // Track pageviews on route changes
  useEffect(() => {
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('config', 'G-NDPVY6TWBK', {
        page_path: location.pathname + location.search,
      });
    }
  }, [location]);

  return (
    <Routes>
      <Route 
        path="/" 
        element={
          <PasswordProtection>
            <Index />
          </PasswordProtection>
        } 
      />
      <Route 
        path="/sff" 
        element={
          <PasswordProtection>
            <SFFWrapped />
          </PasswordProtection>
        } 
      />
      <Route 
        path="/sff/:scope" 
        element={
          <PasswordProtection>
            <SFFPage />
          </PasswordProtection>
        } 
      />
      <Route 
        path="/usa-news" 
        element={
          <PasswordProtection>
            <WrappedNews />
          </PasswordProtection>
        } 
      />
      <Route 
        path="/:identifier" 
        element={
          <PasswordProtection>
            <Wrapped />
          </PasswordProtection>
        } 
      />
    </Routes>
  );
}

export default App;

