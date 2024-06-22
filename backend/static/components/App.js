import React, { useState } from 'react';
import MainPage from './MainPage';
import SiteManagement from './SiteManagement';

const App = () => {
  const [currentPage, setCurrentPage] = useState('main');

  const renderPage = () => {
    switch (currentPage) {
      case 'main':
        return <MainPage />;
      case 'manage-sites':
        return <SiteManagement />;
      default:
        return <MainPage />;
    }
  };

  return (
    <div>
      <nav>
        <ul>
          <li>
            <button onClick={() => setCurrentPage('main')}>Home</button>
          </li>
          <li>
            <button onClick={() => setCurrentPage('manage-sites')}>Manage Sites</button>
          </li>
        </ul>
      </nav>
      {renderPage()}
    </div>
  );
};

export default App;
