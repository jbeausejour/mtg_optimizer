import React, { useContext } from 'react';
import { Menu } from 'antd';
import ThemeContext from './ThemeContext';

const ThemeToggle = () => {
  const { theme, toggleTheme } = useContext(ThemeContext);

  return (
    <Menu.Item onClick={toggleTheme}>
      Switch to {theme === 'light' ? 'dark' : 'light'} mode
    </Menu.Item>
  );
};

export default ThemeToggle;
