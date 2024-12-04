import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Card, Spin, message } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { OptimizationSummary, OptimizationDetails } from './OptimizationDisplay';
import api from '../utils/api';

const ScanResult = () => {
    const { scanId } = useParams();
    const [resultData, setResultData] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchScanResult = async () => {
            try {
                const response = await api.get(`/results/${scanId}`);
                setResultData(response.data);
            } catch (error) {
                console.error('Error fetching scan result:', error);
                message.error('Failed to load scan results');
            } finally {
                setLoading(false);
            }
        };

        fetchScanResult();
    }, [scanId]);

    if (loading) return <Spin size="large" />;
    if (!resultData) return <div>No results found</div>;

    return (
        <div>
            <Button 
                icon={<ArrowLeftOutlined />} 
                onClick={() => navigate('/results')}
                style={{ marginBottom: '20px' }}
            >
                Back to Results
            </Button>

            <Card title={`Scan Details #${scanId}`}>
                <p>Scan Date: {new Date(resultData.created_at || resultData.timestamp).toLocaleString()}</p>
                <p>Cards Scanned: {resultData.cards_scraped}</p>
                <p>Sites Scanned: {resultData.sites_scraped}</p>
            </Card>

            {resultData.optimization && (
                <OptimizationSummary result={resultData.optimization} />
            )}
        </div>
    );
};

export default ScanResult;