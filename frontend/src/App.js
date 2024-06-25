import React from 'react';
import { BrowserRouter as Router, Route, Switch, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import Dashboard from './pages/Dashboard';
import Optimize from './components/Optimize';
import SiteManagement from './components/SiteManagement';
import Results from './components/Results';

const { Header, Content, Footer } = Layout;

function App() {
  return (
    <Router>
      <Layout className="layout">
        <Header>
          <Menu theme="dark" mode="horizontal" defaultSelectedKeys={['1']}>
            <Menu.Item key="1"><Link to="/dashboard">Dashboard</Link></Menu.Item>
            <Menu.Item key="2"><Link to="/optimize">Optimize</Link></Menu.Item>
            <Menu.Item key="3"><Link to="/site-management">Site Management</Link></Menu.Item>
            <Menu.Item key="4"><Link to="/results">Results</Link></Menu.Item>
          </Menu>
        </Header>
        <Content style={{ padding: '0 50px' }}>
          <Switch>
            <Route path="/" exact component={Dashboard} />
            <Route path="/dashboard" component={Dashboard} />
            <Route path="/optimize" component={Optimize} />
            <Route path="/site-management" component={SiteManagement} />
            <Route path="/results" component={Results} />
          </Switch>
        </Content>
        <Footer style={{ textAlign: 'center' }}>MTG Scraper ©2024</Footer>
      </Layout>
    </Router>
  );
}

export default App;
