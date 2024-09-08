import React from 'react';
import { Menu } from 'antd';
import { Link, useLocation } from 'react-router-dom';
import { useTheme } from '../utils/ThemeContext';
import { BulbOutlined } from '@ant-design/icons';

const Navigation = () => {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const menuItems = [
    { key: "/", label: <Link to="/">Dashboard</Link> },
    { key: "/cards", label: <Link to="/cards">Card Management</Link> },
    { key: "/site-management", label: <Link to="/site-management">Site Management</Link> },
    { key: "/optimize", label: <Link to="/optimize">Optimization Center</Link> },
    { key: "/results", label: <Link to="/results">Results & Analytics</Link> },
    { key: "/price-tracker", label: <Link to="/price-tracker">Price Tracker</Link> },
    { key: "/settings", label: <Link to="/settings">Settings</Link> },
    {
        key: "theme",
        label: (
          <BulbOutlined 
            onClick={(e) => {
              e.stopPropagation();
              toggleTheme();
            }} 
            style={{ fontSize: '20px' }}
          />
        ),
        style: { marginLeft: 'auto' }
      }
    ];
  
    return (
      <Menu 
        theme={theme} 
        mode="horizontal" 
        selectedKeys={[location.pathname]} 
        items={menuItems}
      />
    );
  };
  
  export default Navigation;