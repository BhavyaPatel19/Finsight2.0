import { motion } from "motion/react";

/**
 * AnimatedCheckbox — FinSight-themed animated SVG checkbox.
 *
 * Drop-in replacement for <input type="checkbox">.
 * Props:
 *   checked   — boolean
 *   onChange  — function (called with a synthetic-like object { target: { checked } })
 *   size      — px size (default 20)
 *   duration  — animation duration in seconds (default 0.5)
 *   disabled  — boolean
 */
export default function AnimatedCheckbox({
  checked = false,
  onChange,
  size = 20,
  duration = 0.5,
  disabled = false,
  style,
}) {
  const handleClick = (e) => {
    e.stopPropagation();
    if (!disabled && onChange) {
      onChange({ target: { checked: !checked } });
    }
  };

  // Theme tokens keep unchecked boxes visible in both dark and light modes.
  const strokeColor = checked ? "var(--accent-light)" : "var(--checkbox-unchecked)";

  return (
    <div
      onClick={handleClick}
      style={{
        userSelect: "none",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        flexShrink: 0,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        ...style,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        style={{ display: "block" }}
      >
        <motion.path
          d="M 2.45 24.95 V 33.95 C 2.45 35.9382 4.0618 37.55 6.05 37.55 H 33.95 C 35.9382 37.55 37.55 35.9382 37.55 33.95 V 6.05 C 37.55 4.0618 35.9382 2.45 33.95 2.45 H 6.05 C 4.0618 2.45 2.45 4.0618 2.45 6.05 V 22.0617 C 2.45 23.0443 2.8516 23.9841 3.5616 24.6633 L 10.0451 30.8649 C 11.5404 32.2952 13.9308 32.1735 15.2731 30.5988 L 36.2 6.05"
          stroke={strokeColor}
          strokeLinecap="round"
          strokeWidth={3}
          animate={{
            strokeDasharray: checked ? 150 : 132,
            strokeDashoffset: checked ? -134 : 0,
            stroke: strokeColor,
          }}
          transition={{
            duration,
            ease: "easeInOut",
          }}
        />
      </svg>
    </div>
  );
}
