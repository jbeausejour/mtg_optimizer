import React, { useState, useEffect } from 'react';

const SiteForm = ({ show, handleClose, handleSave, editSite }) => {
  const [site, setSite] = useState({ name: '', url: '', parse_method: '', type: '' });

  useEffect(() => {
    if (editSite) {
      setSite(editSite);
    } else {
      setSite({ name: '', url: '', parse_method: '', type: '' });
    }
  }, [editSite]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setSite({ ...site, [name]: value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleSave(editSite ? editSite.id : null, site);
  };

  return (
    <div style={{ display: show ? 'block' : 'none' }}>
      <h2>{editSite ? 'Edit Site' : 'Add New Site'}</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Name</label>
          <input type="text" name="name" value={site.name} onChange={handleChange} required />
        </div>
        <div>
          <label>URL</label>
          <input type="url" name="url" value={site.url} onChange={handleChange} required />
        </div>
        <div>
          <label>Parse Method</label>
          <input type="text" name="parse_method" value={site.parse_method} onChange={handleChange} required />
        </div>
        <div>
          <label>Type</label>
          <input type="text" name="type" value={site.type} onChange={handleChange} required />
        </div>
        <button type="submit">{editSite ? 'Update Site' : 'Add Site'}</button>
        <button type="button" onClick={handleClose}>Cancel</button>
      </form>
    </div>
  );
};

export default SiteForm;
