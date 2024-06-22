import React, { useState } from 'react';

const SiteList = ({ sites, onDelete, onUpdate }) => {
  const [editMode, setEditMode] = useState(null);
  const [editSite, setEditSite] = useState({});

  const handleEdit = (site) => {
    setEditMode(site.id);
    setEditSite(site);
  };

  const handleSave = async () => {
    onUpdate(editMode, editSite);
    setEditMode(null);
  };

  return (
    <div>
      <h2>Sites</h2>
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
            <tr key={site.id}>
              {editMode === site.id ? (
                <>
                  <td>
                    <input
                      type="text"
                      value={editSite.name}
                      onChange={(e) => setEditSite({ ...editSite, name: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={editSite.url}
                      onChange={(e) => setEditSite({ ...editSite, url: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={editSite.parse_method}
                      onChange={(e) => setEditSite({ ...editSite, parse_method: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={editSite.type}
                      onChange={(e) => setEditSite({ ...editSite, type: e.target.value })}
                    />
                  </td>
                  <td>
                    <button onClick={handleSave}>Save</button>
                  </td>
                </>
              ) : (
                <>
                  <td>{site.name}</td>
                  <td>{site.url}</td>
                  <td>{site.parse_method}</td>
                  <td>{site.type}</td>
                  <td>
                    <button onClick={() => handleEdit(site)}>Edit</button>
                    <button onClick={() => onDelete(site.id)}>Delete</button>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default SiteList;
