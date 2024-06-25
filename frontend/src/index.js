import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ThemeProvider from './components/ThemeContext';
import 'antd/dist/reset.css';

const container = document.getElementById('root');
const root = ReactDOM.createRoot(container);

root.render(
  <ThemeProvider>
    <App />
  </ThemeProvider>
);