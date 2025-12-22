import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function SFFHome() {
  const navigate = useNavigate();
  
  useEffect(() => {
    // Redirect immediately to USA page using React Router
    navigate('/sff/usa', { replace: true });
  }, [navigate]);

  // Show loading while redirecting
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white flex items-center justify-center">
      <div className="text-center">
        <div className="text-xl mb-2">Redirecting to SFF page...</div>
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mx-auto"></div>
      </div>
    </div>
  );
}

export default function SFFHomePage() {
  return <SFFHome />;
}

