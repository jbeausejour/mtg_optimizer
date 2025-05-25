import React, { useState, useEffect } from 'react';
import { Slider, Typography, Row, Col, Divider, Tooltip } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

export const weightConfig = {
  cost: {
    label: 'Cost',
    min: 0.1,
    max: 10.0,
    step: 0.1,
    tooltip: 'Prioritize cheaper listings.',
  },
  quality: {
    label: 'Quality',
    min: 0.1,
    max: 10.0,
    step: 0.1,
    tooltip: 'Favor higher quality cards (e.g., NM over PLD).',
  },
  availability: {
    label: 'Availability',
    min: 10,
    max: 1000,
    step: 10,
    tooltip: 'Ensure the full wishlist is completed.',
  },
  store_count: {
    label: 'Minimize Stores',
    min: 0.1,
    max: 5.0,
    step: 0.1,
    tooltip: 'Minimize the number of different stores used.',
  },
};

const NormalizedWeightSliders = ({ onChange, findMinStore = false }) => {
  const [localWeights, setLocalWeights] = useState({
    cost: 4.0,
    store_count: 0.1,
    availability: 0.5,
    quality: 2.5,
  });

  useEffect(() => {
    if (typeof onChange === 'function') {
      onChange((prev) => {
        const isDifferent = Object.keys(localWeights).some(
          (key) => prev[key] !== localWeights[key]
        );
        return isDifferent ? localWeights : prev;
      });
    }
  }, [localWeights, onChange]);

  return (
    <>
      <Divider orientation="left">Set Optimization Weights</Divider>
      {Object.entries(weightConfig).map(([key, config]) => (
        <Row key={key} align="middle" style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Text>
              {config.label}{' '}
              <Tooltip title={config.tooltip}>
                <InfoCircleOutlined />
              </Tooltip>
            </Text>
          </Col>
          <Col span={16}>
            <Slider
              min={config.min}
              max={config.max}
              step={config.step}
              value={localWeights[key]}
              disabled={findMinStore && key === 'store_count'}
              onChange={(val) =>
                setLocalWeights((prev) => ({
                  ...prev,
                  [key]: val,
                }))
              }
              tooltip={{ formatter: (val) => val.toFixed(2) }}
            />
          </Col>
        </Row>
      ))}
    </>
  );
};

export default NormalizedWeightSliders;
