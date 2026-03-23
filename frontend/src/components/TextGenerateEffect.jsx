import { useEffect } from 'react'
import { motion, stagger, useAnimate } from 'motion/react'

/**
 * Fades in text word-by-word with a blur-to-clear effect.
 * Only animates when `animate` prop is true (for the latest message).
 * When `animate` is false, text renders instantly with no animation.
 */
export default function TextGenerateEffect({
  text,
  className = '',
  duration = 0.4,
  staggerDelay = 0.06,
  animate: shouldAnimate = true,
}) {
  const [scope, animateScope] = useAnimate()
  const words = text.split(' ')

  useEffect(() => {
    if (!shouldAnimate) return
    animateScope(
      'span.word',
      { opacity: 1, filter: 'blur(0px)' },
      { duration, delay: stagger(staggerDelay) }
    )
  }, [text, shouldAnimate])

  if (!shouldAnimate) {
    return <span className={className}>{text}</span>
  }

  return (
    <motion.div ref={scope} className={className} style={{ display: 'inline' }}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          className="word"
          style={{
            opacity: 0,
            filter: 'blur(6px)',
            display: 'inline',
          }}
        >
          {word}{i < words.length - 1 ? ' ' : ''}
        </motion.span>
      ))}
    </motion.div>
  )
}
