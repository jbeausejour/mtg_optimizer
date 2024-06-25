import React, { useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { BulbOutlined } from '@ant-design/icons';
import ThemeContext from './components/ThemeContext';
import Dashboard from './pages/Dashboard';
import SiteManagement from './components/SiteManagement';
import Optimize from './components/Optimize';
import Results from './components/Results';
import './App.css';
import './global.css';

const { Header, Content, Footer } = Layout;

function App() {
  const { theme, toggleTheme } = useContext(ThemeContext);

  return (
    <div data-theme={theme} className={`App ${theme}`}>
      <Router>
        <Layout className={`layout ${theme}`}>
          <Header>
            <Menu theme={theme} mode="horizontal" defaultSelectedKeys={['1']}>
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
              <Route path="/" element={<Dashboard />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/site-management" element={<SiteManagement />} />
              <Route path="/optimize" element={<Optimize />} />
              <Route path="/results" element={<Results />} />
            </Routes>
          </Content>
          <Footer className={`ant-layout-footer ${theme}`} style={{ textAlign: 'center' }}>MTG Scraper ©2024</Footer>
        </Layout>
      </Router>
    </div>
  );
}

export default App;
