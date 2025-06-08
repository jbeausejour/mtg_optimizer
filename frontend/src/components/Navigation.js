import React, { useEffect } from 'react';
import { Menu, Dropdown, Avatar, message } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BulbOutlined, UserOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { useAuth } from '../utils/AuthContext';

const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();

  // Hide navigation when the login page is loaded
  useEffect(() => {
    const navbar = document.querySelector('.navbar');
    if (location.pathname === '/login' && navbar) {
      navbar.style.display = 'none';
    } else if (navbar) {
      navbar.style.display = 'block';
    }
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    message.success('Logged out successfully');
    navigate('/login');
  };

  const userMenuItems = [
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">Settings</Link>,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: handleLogout,
    },
  ];

  const menuItems = [
    { key: "/", label: <Link to="/">Dashboard</Link> },
    { key: "/buylist-management", label: <Link to="/buylist-management">Buylist Management</Link> },
    { key: "/site-management", label: <Link to="/site-management">Site Management</Link> },
    { key: "/optimize", label: <Link to="/optimize">Optimization Center</Link> },
    { key: "/results", label: <Link to="/results">Results & Analytics</Link> },
    { key: "/price-tracker", label: <Link to="/price-tracker">Price Tracker</Link> },
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
    },
    {
      key: "user",
      label: (
        <Dropdown menu={{ items: userMenuItems }} trigger={['click']}>
          <Avatar icon={<UserOutlined />} style={{ cursor: 'pointer' }} />
        </Dropdown>
      )
    }
  ];
  
  return (
    <Menu 
      theme={theme} 
      mode="horizontal" 
      selectedKeys={[location.pathname]} 
      items={menuItems}
      style={{
        width: '100%',
        border: 'none', // Remove any borders
        boxShadow: 'none', // Remove shadow that was causing dark bar
      }}
    />
  );
};

export default Navigation;