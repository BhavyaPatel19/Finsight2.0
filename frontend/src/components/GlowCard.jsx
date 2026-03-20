import { GlowingEffect } from "./GlowingEffect";

/**
 * GlowCard — drop-in wrapper that adds the mouse-proximity glow border.
 * All existing className/style props are passed through to the inner div,
 * so .card / .stat-card styles continue to apply unchanged.
 */
export default function GlowCard({ className = "", style, children }) {
  return (
    <div className={`glow-card-wrapper ${className}`} style={style}>
      <GlowingEffect spread={40} proximity={80} borderWidth={1} movementDuration={0.5} />
      {children}
    </div>
  );
}
