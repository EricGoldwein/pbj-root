import React, { createContext, useContext, ReactNode } from 'react';

interface WrappedContextValue {
  username: string;
  avatarUrl?: string;
}

const WrappedContext = createContext<WrappedContextValue | undefined>(undefined);

export const useWrappedContext = () => {
  const context = useContext(WrappedContext);
  if (!context) {
    throw new Error('useWrappedContext must be used within WrappedProvider');
  }
  return context;
};

interface WrappedProviderProps {
  username: string;
  avatarUrl?: string;
  children: ReactNode;
}

export const WrappedProvider: React.FC<WrappedProviderProps> = ({
  username,
  avatarUrl,
  children,
}) => {
  return (
    <WrappedContext.Provider value={{ username, avatarUrl }}>
      {children}
    </WrappedContext.Provider>
  );
};

