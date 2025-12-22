import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PasswordProtection } from '../components/PasswordProtection';

function SFFHome() {
  const navigate = useNavigate();

  useEffect(() => {
    // Redirect to USA page by default
    navigate('/sff/usa', { replace: true });
  }, [navigate]);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <div className="text-center">
        <div className="text-xl mb-2">Loading...</div>
      </div>
    </div>
  );
}

export default function SFFHomePage() {
  return (
    <PasswordProtection password="320">
      <SFFHome />
    </PasswordProtection>
  );
}

