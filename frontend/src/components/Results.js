import React, { useState, useEffect, useContext } from 'react';
import { useParams } from 'react-router-dom';
import { List, Card } from 'antd';
import axios from 'axios';
import ThemeContext from './ThemeContext';
import '../global.css';

const Results = () => {
  const { scanId } = useParams();
  const [results, setResults] = useState([]);
  const { theme } = useContext(ThemeContext);

  useEffect(() => {
    axios.get(`/api/v1/results/${scanId}`)
      .then(response => setResults(response.data))
      .catch(error => console.error('Error fetching results:', error));
  }, [scanId]);

  return (
    <div className={`results section`}>
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
