import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './utils/ThemeContext';
import Layout from './components/Layout';
import Navigation from './components/Navigation';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './pages/Dashboard';
import CardManagement from './pages/CardManagement';
import SiteManagement from './pages/SiteManagement';
import Optimize from './pages/Optimize';
import Results from './pages/Results';
import PriceTracker from './pages/PriceTracker';
import Settings from './pages/Settings';
import ErrorBoundary from './utils/ErrorBoundary';
import './global.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLoginSuccess = (token) => {
    localStorage.setItem('token', token);
    setIsAuthenticated(true);
  };

  const PrivateRoute = ({ children }) => {
    return isAuthenticated ? children : <Navigate to="/login" />;
  };

  return (
    <ThemeProvider>
      <Router>
        <ErrorBoundary>
          <Layout>
            {isAuthenticated && <Navigation />}
            <Routes>
              <Route path="/login" element={
                isAuthenticated ? <Navigate to="/" /> : <Login onLoginSuccess={handleLoginSuccess} />
              } />
              <Route path="/register" element={
                isAuthenticated ? <Navigate to="/" /> : <Register onRegisterSuccess={() => navigate('/login')} />
              } />
              <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
              <Route path="/cards" element={<PrivateRoute><CardManagement /></PrivateRoute>} />
              <Route path="/site-management" element={<PrivateRoute><SiteManagement /></PrivateRoute>} />
              <Route path="/optimize" element={<PrivateRoute><Optimize /></PrivateRoute>} />
              <Route path="/results" element={<PrivateRoute><Results /></PrivateRoute>} />
              <Route path="/price-tracker" element={<PrivateRoute><PriceTracker /></PrivateRoute>} />
              <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
            </Routes>
          </Layout>
        </ErrorBoundary>
      </Router>
    </ThemeProvider>
  );
}

export default App;