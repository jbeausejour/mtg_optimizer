import React from 'react';

const SiteList = ({ sites, onDelete, onUpdate }) => {
  return (
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
            <td>{site.name}</td>
            <td>{site.url}</td>
            <td>{site.parse_method}</td>
            <td>{site.type}</td>
            <td>
              <button onClick={() => onUpdate(site)}>Edit</button>
              <button onClick={() => onDelete(site.id)}>Delete</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

export default SiteList;
