import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider} from '@tanstack/react-query';
import { AuthProvider } from './utils/AuthContext';
import Navigation from './components/Navigation';
import Login from './components/Login';
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
const Layout = ({ children }) => {
  const location = useLocation();
  const showNavbar = location.pathname !== '/login' && location.pathname !== '/register';
  
  return (
    <div className="app-container">
      {showNavbar && <Navigation />}
      <div className="content-container" style={{ 
        marginTop: showNavbar ? '60px' : '0' // Adjust this value based on your navigation height
      }}>
        {children}
      </div>
    </div>
  );
};

function App() {

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <Layout>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route element={<ProtectedRoute />}>
                <Route path="/" element={<Dashboard/>} />
                <Route path="/buylist-management" element={<BuylistManagement/>} />
                <Route path="/site-management" element={<SiteManagement/>} />
                <Route path="/optimize" element={<Optimize/>} />
                <Route path="/results" element={<Results/>} />
                <Route path="/results/:scanId" element={<Results/>} /> {/* Update this line */}
                <Route path="/price-tracker" element={<PriceTracker/>} />
                <Route path="/settings" element={<Settings/>} />
              </Route>
            </Routes>
          </Layout>
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
