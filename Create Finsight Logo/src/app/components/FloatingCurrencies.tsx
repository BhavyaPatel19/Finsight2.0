import { motion } from "motion/react";
import { useMemo } from "react";

const currencySymbols = [
  "$", "€", "£", "¥", "₹", "₩", "₽", "₺", "฿", "₫",
  "₴", "₸", "₦", "₵", "₡", "₲", "₱", "﷼", "₭", "₮",
  "৳", "₪", "₢", "₣", "₤", "₠", "¢", "ƒ", "₯", "₰",
];

interface FloatingItem {
  id: number;
  symbol: string;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  duration: number;
  delay: number;
  size: number;
  opacity: number;
}

export function FloatingCurrencies() {
  const items: FloatingItem[] = useMemo(() => {
    return Array.from({ length: 55 }, (_, i) => {
      const symbol = currencySymbols[i % currencySymbols.length];
      const edge = i % 4;
      let startX: number, startY: number, endX: number, endY: number;
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
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {items.map((item) => (
        <motion.div
          key={item.id}
          className="absolute"
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
            className="text-[#1B2A4A] select-none"
            style={{ fontSize: `${item.size}rem`, fontWeight: 700 }}
          >
            {item.symbol}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
