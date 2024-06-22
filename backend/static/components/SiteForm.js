import React, { useState } from 'react';

const SiteForm = ({ onAdd }) => {
    const [site, setSite] = useState({ name: '', url: '', parse_method: '', type: '' });

    const handleSubmit = async (e) => {
        e.preventDefault();
        onAdd(site);
        setSite({ name: '', url: '', parse_method: '', type: '' });
    };

    return (
        <div>
            <h2>Add New Site</h2>
            <form onSubmit={handleSubmit}>
                <input
                    type="text"
                    placeholder="Name"
                    value={site.name}
                    onChange={(e) => setSite({ ...site, name: e.target.value })}
                    required
                />
                <input
                    type="text"
                    placeholder="URL"
                    value={site.url}
                    onChange={(e) => setSite({ ...site, url: e.target.value })}
                    required
                />
                <input
                    type="text"
                    placeholder="Parse Method"
                    value={site.parse_method}
                    onChange={(e) => setSite({ ...site, parse_method: e.target.value })}
                    required
                />
                <input
                    type="text"
                    placeholder="Type"
                    value={site.type}
                    onChange={(e) => setSite({ ...site, type: e.target.value })}
                    required
                />
                <button type="submit">Add Site</button>
            </form>
        </div>
    );
};

export default SiteForm;
