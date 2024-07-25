import React, { useContext, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { BulbOutlined } from '@ant-design/icons';
import ThemeContext from './utils/ThemeContext';
import ErrorBoundary from './utils/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import SiteManagement from './pages/SiteManagement';
import Optimize from './pages/Optimize';
import Results from './pages/Results';
import './global.css';

const { Header, Content, Footer } = Layout;

function App() {
  const { theme, toggleTheme } = useContext(ThemeContext);
  const [selectedKey, setSelectedKey] = useState('1');

  return (
    <div data-theme={theme} className={`App ${theme}`}>
      <Router>
        <Layout className={`layout ${theme}`}>
          <ErrorBoundary>
            <AppContent theme={theme} toggleTheme={toggleTheme} selectedKey={selectedKey} setSelectedKey={setSelectedKey} />
          </ErrorBoundary>
        </Layout>
      </Router>
    </div>
  );
}

function AppContent({ theme, toggleTheme, selectedKey, setSelectedKey }) {
  const location = useLocation();

  useEffect(() => {
    const pathname = location.pathname;
    if (pathname === '/' || pathname === '/dashboard') setSelectedKey('1');
    else if (pathname === '/site-management') setSelectedKey('2');
    else if (pathname === '/optimize') setSelectedKey('3');
    else if (pathname.startsWith('/results')) setSelectedKey('4');
  }, [location]);

  return (
    <>
      <Header>
        <Menu theme={theme} mode="horizontal" selectedKeys={[selectedKey]}>
          <Menu.Item key="1"><Link to="/">Dashboard</Link></Menu.Item>
          <Menu.Item key="2"><Link to="/site-management">Site Management</Link></Menu.Item>
          <Menu.Item key="3"><Link to="/optimize">Optimize</Link></Menu.Item>
          <Menu.Item key="4"><Link to="/results">Results</Link></Menu.Item>
          <Menu.Item key="5" style={{ marginLeft: 'auto' }}>
            <BulbOutlined onClick={toggleTheme} style={{ fontSize: '20px' }} />
          </Menu.Item>
        </Menu>
      </Header>
      <Content style={{ padding: '0 50px' }}>
      <Routes>
          <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
          <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
          <Route path="/site-management" element={<ErrorBoundary><SiteManagement /></ErrorBoundary>} />
          <Route path="/optimize" element={<ErrorBoundary><Optimize /></ErrorBoundary>} />
          <Route path="/results" element={<ErrorBoundary><Results /></ErrorBoundary>} />
          <Route path="/results/:scanId" element={<ErrorBoundary><Results /></ErrorBoundary>} />
        </Routes>
      </Content>
      <Footer className={`ant-layout-footer ${theme}`} style={{ textAlign: 'center' }}>MTG Scraper ©2024</Footer>
    </>
  );
}

export default App;