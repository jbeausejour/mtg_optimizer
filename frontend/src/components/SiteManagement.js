import React, { useState, useEffect } from 'react';
import SiteList from './SiteList';
import SiteForm from './SiteForm';

const SiteManagement = () => {
  const [sites, setSites] = useState([]);
  const [show, setShow] = useState(false);
  const [editSite, setEditSite] = useState(null);

  useEffect(() => {
    fetchSiteList();
  }, []);

  const fetchSiteList = async () => {
    try {
      const response = await fetch('/get_site_list');
      if (response.ok) {
        const data = await response.json();
        setSites(data);
      } else {
        console.error('Failed to fetch site list:', response.status);
      }
    } catch (error) {
      console.error('Error fetching site list:', error);
    }
  };

  const handleAddSite = async (newSite) => {
    try {
      const response = await fetch('/add_site', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSite)
      });
      if (response.ok) {
        fetchSiteList();
        handleClose();
      } else {
        console.error('Failed to add site:', response.status);
      }
    } catch (error) {
      console.error('Error adding site:', error);
    }
  };

  const handleUpdateSite = async (id, updatedSite) => {
    try {
      const response = await fetch(`/update_site/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedSite)
      });
      if (response.ok) {
        fetchSiteList();
        handleClose();
      } else {
        console.error('Failed to update site:', response.status);
      }
    } catch (error) {
      console.error('Error updating site:', error);
    }
  };

  const handleDeleteSite = async (id) => {
    try {
      const response = await fetch(`/delete_site/${id}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        fetchSiteList();
      } else {
        console.error('Failed to delete site:', response.status);
      }
    } catch (error) {
      console.error('Error deleting site:', error);
    }
  };

  const handleClose = () => setShow(false);
  const handleShow = (site = null) => {
    setEditSite(site);
    setShow(true);
  };

  return (
    <div>
      <h1>Site Management</h1>
      <button onClick={() => handleShow()}>Add New Site</button>
      <SiteList sites={sites} onDelete={handleDeleteSite} onUpdate={handleShow} />
      <SiteForm
        show={show}
        handleClose={handleClose}
        handleSave={editSite ? handleUpdateSite : handleAddSite}
        editSite={editSite}
      />
    </div>
  );
};

export default SiteManagement;
