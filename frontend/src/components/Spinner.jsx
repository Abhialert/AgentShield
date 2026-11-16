import React from 'react'

export default function Spinner({ size = 'sm' }) {
  const sz = size === 'lg' ? '2rem' : size === 'md' ? '1.5rem' : '1rem'
  return (
    <span
      className="spinner"
      style={{ width: sz, height: sz, borderWidth: size === 'lg' ? '3px' : '2px' }}
    />
  )
}

