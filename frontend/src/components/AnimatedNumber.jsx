import React, { useEffect, useState, useRef } from 'react'

export default function AnimatedNumber({ value }) {
  const [display, setDisplay] = useState(value)
  const [flash, setFlash]     = useState(false)
  const prevRef = useRef(value)

  useEffect(() => {
    if (value === prevRef.current) return
    prevRef.current = value
    setFlash(true)
    const start = display
    const end   = value
    const diff  = end - start
    const steps = 20
    let step = 0
    const timer = setInterval(() => {
      step++
      setDisplay(Math.round(start + (diff * step) / steps))
      if (step >= steps) {
        clearInterval(timer)
        setDisplay(end)
        setTimeout(() => setFlash(false), 800)
      }
    }, 20)
    return () => clearInterval(timer)
  }, [value])

  return (
    <span className={flash ? 'num-updated' : ''}>
      {display.toLocaleString()}
    </span>
  )
}

