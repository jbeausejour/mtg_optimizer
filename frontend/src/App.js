import React from 'react';
import { BrowserRouter as Router, Route, Switch, Link } from 'react-router-dom';
import MainPage from './components/MainPage';
import Dashboard from './pages/Dashboard';
import SiteManagement from './components/SiteManagement';

function App() {
  return (
    <Router>
      <nav>
        <ul>
          <li><Link to="/">Home</Link></li>
          <li><Link to="/dashboard">Dashboard</Link></li>
          <li><Link to="/site-management">Site Management</Link></li>
        </ul>
      </nav>
      <Switch>
        <Route path="/" exact component={MainPage} />
        <Route path="/dashboard" component={Dashboard} />
        <Route path="/site-management" component={SiteManagement} />
      </Switch>
    </Router>
  );
}

export default App;