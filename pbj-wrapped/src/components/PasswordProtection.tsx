import React, { useState, useEffect } from 'react';

const CORRECT_PASSWORD = '320-7676';

interface PasswordProtectionProps {
  children: React.ReactNode;
  password?: string; // Optional custom password
}

export const PasswordProtection: React.FC<PasswordProtectionProps> = ({ children, password: customPassword }) => {
  const correctPassword = customPassword || CORRECT_PASSWORD;
  // Use password-specific sessionStorage key to prevent cross-authentication
  const storageKey = `pbj_wrapped_authenticated_${correctPassword}`;
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    // Check if user is already authenticated with the correct password for this route
    const authStatus = sessionStorage.getItem(storageKey);
    if (authStatus === 'true') {
      setIsAuthenticated(true);
    }
  }, [storageKey]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (passwordInput === correctPassword) {
      setIsAuthenticated(true);
      sessionStorage.setItem(storageKey, 'true');
    } else {
      setError('Incorrect password. Please try again.');
      setPasswordInput('');
    }
  };

  if (isAuthenticated) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900">
      <div className="max-w-md w-full mx-4">
        <div className="bg-gray-800/90 backdrop-blur-sm rounded-2xl shadow-2xl p-8 border border-gray-700">
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-white mb-2">PBJ Wrapped</h1>
            <p className="text-gray-300">Please enter the password to continue</p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <input
                type="password"
                value={passwordInput}
                onChange={(e) => {
                  setPasswordInput(e.target.value);
                  setError('');
                }}
                placeholder="Enter password"
                className="w-full px-4 py-3 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
                autoFocus
              />
              {error && (
                <p className="mt-2 text-sm text-red-400">{error}</p>
              )}
            </div>
            
            <button
              type="submit"
              className="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              Access Wrapped
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

