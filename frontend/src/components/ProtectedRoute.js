import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';

const ProtectedRoute = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
