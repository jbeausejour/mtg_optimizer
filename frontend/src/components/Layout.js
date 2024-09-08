import React, { useEffect } from 'react';
import { Layout as AntLayout } from 'antd';
import { useTheme } from '../utils/ThemeContext';

const { Header, Content, Footer } = AntLayout;

const Layout = ({ children }) => {
  const { theme } = useTheme();

  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <AntLayout className={`layout ${theme}`}>
      <Header>
        {children[0]} {/* This will be the Navigation component */}
      </Header>
      <Content style={{ padding: '0 50px', minHeight: 'calc(100vh - 134px)' }}>
        {children.slice(1)} {/* This will be the Routes */}
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        MTG Card Optimizer ©{new Date().getFullYear()} Created by Your Name
      </Footer>
    </AntLayout>
  );
};

export default Layout;