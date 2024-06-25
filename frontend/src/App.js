import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import ThemeContext from './components/ThemeContext';
import ThemeToggle from './components/ThemeToggle';
import Dashboard from './pages/Dashboard';
import SiteManagement from './components/SiteManagement';
import Optimize from './components/Optimize';
import Results from './components/Results';
import './App.css';

const { Header, Content, Footer } = Layout;

function App() {
  const [theme, setTheme] = useState('light');

  const toggleTheme = () => {
    setTheme((prevTheme) => (prevTheme === 'light' ? 'dark' : 'light'));
  };


return (
  <ThemeContext.Provider value={{ theme, toggleTheme }}>
    <div data-theme={theme} className="App">
      <Router>
        <Layout className="layout">
          <Header>
            <Menu theme={theme} mode="horizontal" defaultSelectedKeys={['1']}>
              <Menu.Item key="1"><Link to="/">Home</Link></Menu.Item>
              <Menu.Item key="2"><Link to="/dashboard">Dashboard</Link></Menu.Item>
              <Menu.Item key="3"><Link to="/site-management">Site Management</Link></Menu.Item>
              <Menu.Item key="4"><Link to="/optimize">Optimize</Link></Menu.Item>
              <Menu.Item key="5"><Link to="/results">Results</Link></Menu.Item>
              <ThemeToggle />
            </Menu>
          </Header>
          <Content style={{ padding: '0 50px' }}>
            <Routes>
              <Route path="/" element={<MainPage />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/site-management" element={<SiteManagement />} />
              <Route path="/optimize" element={<Optimize />} />
              <Route path="/results" element={<Results />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: 'center' }}>MTG Scraper ©2024</Footer>
        </Layout>
      </Router>
    </div>
  </ThemeContext.Provider>
  );
}

export default App;