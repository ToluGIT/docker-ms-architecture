import React from 'react';

const Logo = ({ size = 40, color = 'white' }) => (
  <svg width={size} height={size} viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M25 5L5 15V35L25 45L45 35V15L25 5Z" stroke={color} strokeWidth="2" />
    <path d="M25 5V25M25 25V45M25 25L5 15M25 25L45 15" stroke={color} strokeWidth="2" />
    <circle cx="25" cy="25" r="6" fill={color} />
    <circle cx="5" cy="15" r="3" fill={color} />
    <circle cx="45" cy="15" r="3" fill={color} />
    <circle cx="5" cy="35" r="3" fill={color} />
    <circle cx="45" cy="35" r="3" fill={color} />
  </svg>
);

export default Logo;
