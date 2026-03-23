import { motion } from "motion/react";
import { useMemo } from "react";

const currencySymbols = [
  "$", "\u20AC", "\u00A3", "\u00A5", "\u20B9", "\u20A9", "\u20BD", "\u20BA", "\u0E3F", "\u20AB",
  "\u20B4", "\u20B8", "\u20A6", "\u20B5", "\u20A1", "\u20B2", "\u20B1", "\uFDFC", "\u20AD", "\u20AE",
  "\u09F3", "\u20AA", "\u20A2", "\u20A3", "\u20A4", "\u20A0", "\u00A2", "\u0192", "\u20AF", "\u20B0",
];

export function FloatingCurrencies({ theme = 'light' }) {
  const items = useMemo(() => {
    return Array.from({ length: 55 }, (_, i) => {
      const symbol = currencySymbols[i % currencySymbols.length];
      const edge = i % 4;
      let startX, startY, endX, endY;
      const randY = () => Math.random() * 100;
      const randX = () => Math.random() * 100;

      if (edge === 0) {
        startX = -8; startY = randY(); endX = 108; endY = randY();
      } else if (edge === 1) {
        startX = 108; startY = randY(); endX = -8; endY = randY();
      } else if (edge === 2) {
        startX = randX(); startY = -8; endX = randX(); endY = 108;
      } else {
        startX = randX(); startY = 108; endX = randX(); endY = -8;
      }

      return {
        id: i,
        symbol,
        startX, startY, endX, endY,
        duration: 16 + Math.random() * 22,
        delay: Math.random() * 14,
        size: 1 + Math.random() * 1.6,
        opacity: 0.1 + Math.random() * 0.12,
      };
    });
  }, []);

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      pointerEvents: 'none',
      overflow: 'hidden',
      zIndex: 0,
    }}>
      {items.map((item) => (
        <motion.div
          key={item.id}
          style={{ position: 'absolute' }}
          initial={{
            left: `${item.startX}%`,
            top: `${item.startY}%`,
            opacity: 0,
          }}
          animate={{
            left: [`${item.startX}%`, `${item.endX}%`],
            top: [`${item.startY}%`, `${item.endY}%`],
            opacity: [0, item.opacity, item.opacity, 0],
          }}
          transition={{
            duration: item.duration,
            delay: item.delay,
            repeat: Infinity,
            ease: "linear",
          }}
        >
          <span
            style={{
              color: theme === 'dark' ? 'rgba(26, 188, 156, 0.6)' : 'rgba(20, 143, 119, 0.25)',
              fontSize: `${item.size}rem`,
              fontWeight: 700,
              userSelect: 'none',
            }}
          >
            {item.symbol}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
