import React, { useState, useEffect } from 'react';
import SiteList from './SiteList';
import SiteForm from './SiteForm';

const SiteManagement = () => {
  const [sites, setSites] = useState([]);

  useEffect(() => {
    fetchSiteList();
  }, []);

  const fetchSiteList = async () => {
    const response = await fetch('/get_site_list');
    const data = await response.json();
    setSites(data);
  };

  const handleAddSite = async (newSite) => {
    const response = await fetch('/add_site', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSite)
    });
    if (response.ok) {
      fetchSiteList();
    }
  };

  const handleUpdateSite = async (updatedSite) => {
    const response = await fetch(`/update_site/${updatedSite.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedSite)
    });
    if (response.ok) {
      fetchSiteList();
    }
  };

  const handleDeleteSite = async (id) => {
    const response = await fetch(`/delete_site/${id}`, {
      method: 'DELETE'
    });
    if (response.ok) {
      fetchSiteList();
    }
  };

  return (
    <div>
      <h1>Site Management</h1>
      <SiteForm onAdd={handleAddSite} />
      <SiteList sites={sites} onDelete={handleDeleteSite} onUpdate={handleUpdateSite} />
    </div>
  );
};

export default SiteManagement;
