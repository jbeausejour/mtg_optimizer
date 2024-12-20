import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './utils/AuthContext';
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
import ProtectedRoute from './components/ProtectedRoute';

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
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    // Check if user is already logged in
    const storedUserId = localStorage.getItem('userId');
    if (storedUserId) {
      console.log('User is :', storedUserId);
      setUserId(storedUserId);
    }
  }, []);

  const handleLogin = (userId) => {
    setUserId(userId);
    console.log('Setting User to :', userId); // Corrected variable name
    localStorage.setItem('userId', userId);
  };

  return (
    <AuthProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/login" element={<Login onLogin={handleLogin} />} />
            <Route path="/register" element={<Register />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<Dashboard  userId={userId} />} />
              <Route path="/card-management" element={<CardManagement userId={userId} />} />
              <Route path="/site-management" element={<SiteManagement  userId={userId} />} />
              <Route path="/optimize" element={<Optimize  userId={userId} />} />
              <Route path="/results" element={<Results  userId={userId} />} />
              <Route path="/results/:scanId" element={<Results  userId={userId} />} /> {/* Update this line */}
              <Route path="/price-tracker" element={<PriceTracker  userId={userId} />} />
              <Route path="/settings" element={<Settings  userId={userId} />} />
            </Route>
          </Routes>
        </Layout>
      </Router>
    </AuthProvider>
  );
}

export default App;
