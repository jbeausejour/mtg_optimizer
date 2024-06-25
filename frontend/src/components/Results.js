import React, { useState, useEffect } from 'react';
import { List, Card } from 'antd';

const Results = () => {
  const [results, setResults] = useState([]);

  useEffect(() => {
    fetch('/api/results')
      .then(response => response.json())
      .then(data => setResults(data))
      .catch(error => console.error('Error fetching results:', error));
  }, []);

  return (
    <div>
      <h1>Optimization Results</h1>
      <List
        bordered
        dataSource={results}
        renderItem={result => (
          <List.Item>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </List.Item>
        )}
      />
    </div>
  );
};

export default Results;
