import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider} from '@tanstack/react-query';
// REMOVED: ConfigProvider import since it's now in ThemeProvider
import { AuthProvider } from './utils/AuthContext';
import { SettingsProvider } from './utils/SettingsContext';
import { NotificationProvider } from './utils/NotificationContext';
import Navigation from './components/Navigation';
import Login from './components/Login';
import Layout from './components/Layout';
import Register from './components/Register';
import Dashboard from './pages/Dashboard';
import BuylistManagement from './pages/CardManagement';
import SiteManagement from './pages/SiteManagement';
import Optimize from './pages/Optimize';
import Results from './pages/Results';
import PriceTracker from './pages/PriceTracker';
import Settings from './pages/Settings';
import ProtectedRoute from './components/ProtectedRoute';

// Initialize a new QueryClient
const queryClient = new QueryClient();

// Custom Hook to conditionally render navigation based on route
const RouterContent = () => {
  const location = useLocation();
  const showNavbar = location.pathname !== '/login' && location.pathname !== '/register';
  
  // For login/register pages, render without Layout
  if (!showNavbar) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Routes>
    );
  }
  
  // For other pages, use Layout with Navigation
  return (
    <Layout>
      {[
        <Navigation key="nav" />,
        <Routes key="routes">
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Dashboard/>} />
            <Route path="/buylist-management" element={<BuylistManagement/>} />
            <Route path="/site-management" element={<SiteManagement/>} />
            <Route path="/optimize" element={<Optimize/>} />
            <Route path="/results" element={<Results/>} />
            <Route path="/results/:scanId" element={<Results/>} />
            <Route path="/price-tracker" element={<PriceTracker/>} />
            <Route path="/settings" element={<Settings/>} />
          </Route>
        </Routes>
      ]}
    </Layout>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* ConfigProvider is now handled in ThemeProvider */}
      <NotificationProvider>
        <SettingsProvider>
          <AuthProvider>
            <Router>
              <RouterContent />
            </Router>
          </AuthProvider>  
        </SettingsProvider>
      </NotificationProvider>
    </QueryClientProvider>
  );
}

export default App;