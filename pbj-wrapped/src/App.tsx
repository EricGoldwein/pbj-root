import { Routes, Route, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Index from './pages/Index';
import Wrapped from './pages/wrapped';
import WrappedNews from './pages/wrapped-news';
import SFFPage from './pages/sff-page';
import SFFHomePage from './pages/sff-home';

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
        element={<Index />}
      />
      <Route 
        path="/wrapped" 
        element={<Index />}
      />
      <Route 
        path="/wrapped/usa" 
        element={<Wrapped />}
      />
      <Route 
        path="/wrapped/:identifier" 
        element={<Wrapped />}
      />
      <Route 
        path="/sff" 
        element={<SFFHomePage />}
      />
      <Route 
        path="/sff/usa" 
        element={<SFFPage />}
      />
      <Route 
        path="/sff/:scope" 
        element={<SFFPage />}
      />
      <Route 
        path="/usa-news" 
        element={<WrappedNews />}
      />
    </Routes>
  );
}

export default App;

