import React from 'react';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

const RadarChart = ({ weights, weightConfig }) => {
  const data = {
    labels: ['Cost', 'Store Count', 'Availability', 'Quality'],
    datasets: [
      {
        label: 'Weight Importance (%)',
        data: [
          (weights.cost / weightConfig.cost.max) * 100,
          (weights.store_count / weightConfig.store_count.max) * 100,
          (weights.availability / weightConfig.availability.max) * 100,
          (weights.quality / weightConfig.quality.max) * 100,
        ],
        backgroundColor: 'rgba(22, 119, 255, 0.2)',
        borderColor: 'rgba(22, 119, 255, 1)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(22, 119, 255, 1)',
      },
    ],
  };

  const options = {
    responsive: true,
    scales: {
      r: {
        angleLines: { display: true },
        suggestedMin: 0,
        suggestedMax: 100,
        ticks: {
          beginAtZero: true,
          stepSize: 20,
          callback: value => `${value}%`,
        },
        pointLabels: {
          font: { size: 14 },
        },
      },
    },
    plugins: {
      legend: { display: false },
    },
  };

  return <Radar data={data} options={options} />;
};

export default RadarChart;
