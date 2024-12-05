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

  const userMenu = (
    <Menu>
      <Menu.Item key="settings" icon={<SettingOutlined />}>
        <Link to="/settings">Settings</Link>
      </Menu.Item>
      <Menu.Item key="logout" icon={<LogoutOutlined />} onClick={handleLogout}>
        Logout
      </Menu.Item>
    </Menu>
  );

  const menuItems = [
    { key: "/", label: <Link to="/">Dashboard</Link> },
    { key: "/card-management", label: <Link to="/card-management">Card Management</Link> },
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
        <Dropdown overlay={userMenu} trigger={['click']}>
          <Avatar icon={<UserOutlined />} style={{ cursor: 'pointer' }} />
        </Dropdown>
      )
    }
  ];
  
  return (
    <nav style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100%',
      backgroundColor: '#fff', // or your preferred color
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      zIndex: 1000,
    }}>
      <Menu 
        theme={theme} 
        mode="horizontal" 
        selectedKeys={[location.pathname]} 
        items={menuItems}
      />
    </nav>
  );
};

export default Navigation;
