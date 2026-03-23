import { motion, AnimatePresence } from "motion/react";
import { useState, useEffect } from "react";

type LogoSize = "small" | "default" | "large" | "xl";
type LogoVariant = "full" | "icon" | "wordmark";
type LogoTheme = "light" | "dark";

interface FinSightLogoProps {
  className?: string;
  size?: LogoSize;
  variant?: LogoVariant;
  theme?: LogoTheme;
  animated?: boolean;
  showTagline?: boolean;
}

const sizeConfig = {
  small:   { icon: 40, text: "1.1rem",  tagline: "0.45rem", gap: 6  },
  default: { icon: 64, text: "1.75rem", tagline: "0.55rem", gap: 10 },
  large:   { icon: 90, text: "2.5rem",  tagline: "0.7rem",  gap: 14 },
  xl:      { icon: 130, text: "3.5rem", tagline: "0.85rem", gap: 18 },
};

// Professional finance palette
const NAVY = "#1B2A4A";
const DARK_TEAL = "#1A5276";
const TEAL = "#148F77";
const LIGHT_TEAL = "#1ABC9C";
const BLUE = "#2980B9";
const STEEL = "#5D6D7E";

export function FinSightLogo({
  className = "",
  size = "default",
  variant = "full",
  theme = "light",
  animated = true,
  showTagline = false,
}: FinSightLogoProps) {
  const [isBlinking, setIsBlinking] = useState(false);
  const cfg = sizeConfig[size];
  const textColor = theme === "dark" ? "#E8EDF2" : NAVY;

  // Blink loop
  useEffect(() => {
    if (!animated) return;
    const interval = setInterval(() => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 200);
    }, 3500);
    return () => clearInterval(interval);
  }, [animated]);

  const IconMark = () => (
    <svg
      width={cfg.icon}
      height={cfg.icon}
      viewBox="0 0 120 120"
      fill="none"
      className="shrink-0"
    >
      <defs>
        <linearGradient id={`barGrad1-${size}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={BLUE} />
          <stop offset="100%" stopColor={DARK_TEAL} />
        </linearGradient>
        <linearGradient id={`barGrad2-${size}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={TEAL} />
          <stop offset="100%" stopColor={DARK_TEAL} />
        </linearGradient>
        <linearGradient id={`barGrad3-${size}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={LIGHT_TEAL} />
          <stop offset="100%" stopColor={TEAL} />
        </linearGradient>
        <linearGradient id={`eyeGrad-${size}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={NAVY} />
          <stop offset="100%" stopColor={DARK_TEAL} />
        </linearGradient>
        <linearGradient id={`irisGrad-${size}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={BLUE} />
          <stop offset="100%" stopColor={LIGHT_TEAL} />
        </linearGradient>
        <linearGradient id={`waveGrad-${size}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={TEAL} />
          <stop offset="100%" stopColor={LIGHT_TEAL} />
        </linearGradient>
      </defs>

      {/* Bar Chart - 3 bars growing upward */}
      <motion.rect
        x="4" y="68" width="14" height="42" rx="3"
        fill={`url(#barGrad1-${size})`}
        initial={animated ? { scaleY: 0 } : false}
        animate={{ scaleY: 1 }}
        transition={{ delay: 0.1, duration: 0.6, ease: "easeOut" }}
        style={{ transformOrigin: "11px 110px" }}
      />
      <motion.rect
        x="22" y="46" width="14" height="64" rx="3"
        fill={`url(#barGrad2-${size})`}
        initial={animated ? { scaleY: 0 } : false}
        animate={{ scaleY: 1 }}
        transition={{ delay: 0.25, duration: 0.6, ease: "easeOut" }}
        style={{ transformOrigin: "29px 110px" }}
      />
      <motion.rect
        x="40" y="28" width="14" height="82" rx="3"
        fill={`url(#barGrad3-${size})`}
        initial={animated ? { scaleY: 0 } : false}
        animate={{ scaleY: 1 }}
        transition={{ delay: 0.4, duration: 0.6, ease: "easeOut" }}
        style={{ transformOrigin: "47px 110px" }}
      />

      {/* Flowing wave connecting bars to eye */}
      <motion.path
        d="M 10 68 C 20 50, 35 35, 50 40 C 60 43, 58 55, 68 50 C 78 45, 82 38, 95 42"
        stroke={`url(#waveGrad-${size})`}
        strokeWidth="3.5"
        strokeLinecap="round"
        fill="none"
        initial={animated ? { pathLength: 0, opacity: 0 } : false}
        animate={{ pathLength: 1, opacity: 0.7 }}
        transition={{ delay: 0.6, duration: 0.8, ease: "easeInOut" }}
      />

      {/* Eye shape - upper lid */}
      <motion.path
        d="M 52 58 C 62 30, 100 30, 110 58"
        stroke={`url(#eyeGrad-${size})`}
        strokeWidth="4.5"
        strokeLinecap="round"
        fill="none"
        initial={animated ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.5, duration: 0.6 }}
      />
      {/* Eye shape - lower lid */}
      <motion.path
        d="M 52 58 C 62 86, 100 86, 110 58"
        stroke={`url(#eyeGrad-${size})`}
        strokeWidth="4.5"
        strokeLinecap="round"
        fill="none"
        initial={animated ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.6, duration: 0.6 }}
      />

      {/* Blinking eyelid */}
      <AnimatePresence>
        {isBlinking && (
          <motion.ellipse
            cx="81"
            cy="58"
            rx="30"
            ry="2"
            fill={theme === "dark" ? "#0D1B2A" : "#f0f2f5"}
            initial={{ ry: 2 }}
            animate={{ ry: 30 }}
            exit={{ ry: 2 }}
            transition={{ duration: 0.1 }}
          />
        )}
      </AnimatePresence>

      {/* Iris */}
      <motion.circle
        cx="81"
        cy="58"
        r="14"
        fill={`url(#irisGrad-${size})`}
        initial={animated ? { scale: 0 } : false}
        animate={{ scale: 1 }}
        transition={{ delay: 0.9, type: "spring", stiffness: 200 }}
      />
      {/* Pupil */}
      <motion.circle
        cx="81"
        cy="58"
        r="7"
        fill={NAVY}
        initial={animated ? { scale: 0 } : false}
        animate={{ scale: 1 }}
        transition={{ delay: 1, type: "spring", stiffness: 200 }}
      />
      {/* Light reflection */}
      <motion.circle
        cx="76"
        cy="53"
        r="3"
        fill="white"
        opacity="0.7"
        initial={animated ? { scale: 0 } : false}
        animate={{ scale: 1 }}
        transition={{ delay: 1.1 }}
      />

      {/* Small data nodes */}
      {[[105, 42], [112, 52], [108, 72]].map(([cx, cy], i) => (
        <motion.circle
          key={i}
          cx={cx}
          cy={cy}
          r="2.5"
          fill={LIGHT_TEAL}
          initial={animated ? { scale: 0 } : false}
          animate={{ scale: 1 }}
          transition={{ delay: 1.2 + i * 0.1 }}
        />
      ))}
      {/* Node connecting lines */}
      <motion.path
        d="M105 42 L110 58 L108 72"
        stroke={LIGHT_TEAL}
        strokeWidth="1"
        fill="none"
        opacity="0.5"
        initial={animated ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={{ delay: 1.3, duration: 0.4 }}
      />
    </svg>
  );

  const WordMark = () => (
    <div className="flex flex-col">
      <div style={{ fontSize: cfg.text, lineHeight: 1.1 }} className="tracking-tight select-none">
        <span style={{ color: textColor, fontWeight: 700 }}>Fin</span>
        <span style={{ color: TEAL, fontWeight: 400 }}>Sight</span>
      </div>
      {showTagline && (
        <span
          className="uppercase tracking-[0.25em] block mt-0.5"
          style={{ fontSize: cfg.tagline, color: STEEL }}
        >
          Financial Analysis Dashboard
        </span>
      )}
    </div>
  );

  if (variant === "icon") return <div className={className}><IconMark /></div>;
  if (variant === "wordmark") return <div className={className}><WordMark /></div>;

  return (
    <div className={`flex items-center ${className}`} style={{ gap: cfg.gap }}>
      <IconMark />
      <WordMark />
    </div>
  );
}
