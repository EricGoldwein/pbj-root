import React, { createContext, useContext, ReactNode } from 'react';

interface WrappedContextValue {
  scope: string;
  name: string;
  identifier?: string;
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
  scope: string;
  name: string;
  identifier?: string;
  children: ReactNode;
}

export const WrappedProvider: React.FC<WrappedProviderProps> = ({
  scope,
  name,
  identifier,
  children,
}) => {
  return (
    <WrappedContext.Provider value={{ scope, name, identifier }}>
      {children}
    </WrappedContext.Provider>
  );
};









