import React, { useContext } from 'react';
import { Button } from 'antd';
import ThemeContext from './ThemeContext';

const ThemeToggle = () => {
  const { theme, toggleTheme } = useContext(ThemeContext);

  return (
    <Button onClick={toggleTheme}>
      {theme === 'light' ? 'Switch to Dark Theme' : 'Switch to Light Theme'}
    </Button>
  );
};

export default ThemeToggle;
