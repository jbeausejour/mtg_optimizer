import React, { useState } from 'react';

const SiteList = ({ sites, onDelete, onUpdate }) => {
  const [editSiteId, setEditSiteId] = useState(null);
  const [editFormData, setEditFormData] = useState({
    name: '',
    url: '',
    parse_method: '',
    type: ''
  });

  const handleEditClick = (site) => {
    setEditSiteId(site.id);
    setEditFormData(site);
  };

  const handleEditChange = (e) => {
    const { name, value } = e.target;
    setEditFormData({ ...editFormData, [name]: value });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    onUpdate(editFormData);
    setEditSiteId(null);
  };

  const handleCancelClick = () => {
    setEditSiteId(null);
  };

  return (
    <div>
      <h2>Site List</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>URL</th>
            <th>Parse Method</th>
            <th>Type</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sites.map((site) => (
            editSiteId === site.id ? (
              <tr key={site.id}>
                <td><input type="text" name="name" value={editFormData.name} onChange={handleEditChange} /></td>
                <td><input type="text" name="url" value={editFormData.url} onChange={handleEditChange} /></td>
                <td><input type="text" name="parse_method" value={editFormData.parse_method} onChange={handleEditChange} /></td>
                <td><input type="text" name="type" value={editFormData.type} onChange={handleEditChange} /></td>
                <td>
                  <button onClick={handleEditSubmit}>Confirm</button>
                  <button onClick={handleCancelClick}>Cancel</button>
                </td>
              </tr>
            ) : (
              <tr key={site.id}>
                <td>{site.name}</td>
                <td>{site.url}</td>
                <td>{site.parse_method}</td>
                <td>{site.type}</td>
                <td>
                  <button onClick={() => handleEditClick(site)}>Edit</button>
                  <button onClick={() => onDelete(site.id)}>Delete</button>
                </td>
              </tr>
            )
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default SiteList;
