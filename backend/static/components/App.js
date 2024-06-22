import React, { useState, useEffect } from 'react';
import SiteForm from './SiteForm';

const App = () => {
    const [sites, setSites] = useState([]);

    useEffect(() => {
        fetch('/get_site_list')
            .then(response => response.json())
            .then(data => setSites(data));
    }, []);

    const handleAddSite = (site) => {
        fetch('/add_site', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(site),
        })
        .then(response => response.json())
        .then(newSite => setSites([...sites, newSite]));
    };

    return (
        <div>
            <h1>MTG Optimizer</h1>
            <SiteForm onAdd={handleAddSite} />
            <ul>
                {sites.map(site => (
                    <li key={site.id}>{site.name}</li>
                ))}
            </ul>
        </div>
    );
};

export default App;
