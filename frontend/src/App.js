import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './utils/ThemeContext';
import Layout from './components/Layout';
import Navigation from './components/Navigation';
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
  return (
    <ThemeProvider>
      <Router>
        <ErrorBoundary>
          <Layout>
            <Navigation />
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/cards" element={<CardManagement />} />
              <Route path="/site-management" element={<SiteManagement />} />
              <Route path="/optimize" element={<Optimize />} />
              <Route path="/results" element={<Results />} />
              <Route path="/price-tracker" element={<PriceTracker />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Layout>
        </ErrorBoundary>
      </Router>
    </ThemeProvider>
  );
}

export default App;