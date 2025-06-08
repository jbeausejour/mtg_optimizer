import React from 'react';
import { Button, Tooltip } from 'antd';
import { MoonOutlined, SunOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';

const ThemeToggle = () => {
  const { theme, toggleTheme } = useTheme(); // Using your existing theme context
  
  return (
    <Tooltip title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
      <Button 
        type="text" 
        icon={theme === 'dark' ? <SunOutlined /> : <MoonOutlined />}
        onClick={toggleTheme}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {theme === 'dark' ? 'Light' : 'Dark'}
      </Button>
    </Tooltip>
  );
};

export default ThemeToggle;