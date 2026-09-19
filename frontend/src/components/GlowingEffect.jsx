import { memo, useCallback, useEffect, useRef } from "react";
import { animate } from "motion/react";

// FinSight-adapted gradient:
// Teal (#148F77) → Blue (#2980B9) → Indigo (#6366f1) → Dark-Teal (#1A5276) → Light-Teal (#1ABC9C)
// A little different from the logo — indigo gives it a premium, slightly alien pop.
const FINSIGHT_GRADIENT = `
  radial-gradient(circle, #1ABC9C 10%, #1ABC9C00 20%),
  radial-gradient(circle at 40% 40%, #2980B9 5%, #2980B900 15%),
  radial-gradient(circle at 60% 60%, #6366f1 10%, #6366f100 20%),
  radial-gradient(circle at 40% 60%, #1A5276 10%, #1A527600 20%),
  repeating-conic-gradient(
    from 236.84deg at 50% 50%,
    #1ABC9C    0%,
    #2980B9    calc(25% / 5),
    #6366f1    calc(50% / 5),
    #1A5276    calc(75% / 5),
    #1ABC9C    calc(100% / 5)
  )
`.trim();

const cn = (...classes) => classes.filter(Boolean).join(" ");

const GlowingEffect = memo(({
  blur = 0,
  inactiveZone = 0.7,
  proximity = 64,
  spread = 40,
  glow: _glow = false,
  className,
  movementDuration = 2,
  borderWidth = 1,
  disabled = false,
}) => {
  const containerRef = useRef(null);
  const lastPosition = useRef({ x: 0, y: 0 });
  const animationFrameRef = useRef(0);

  const handleMove = useCallback(
    (e) => {
      if (!containerRef.current) return;
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);

      animationFrameRef.current = requestAnimationFrame(() => {
        const element = containerRef.current;
        if (!element) return;

        const { left, top, width, height } = element.getBoundingClientRect();
        const mouseX = e?.x ?? lastPosition.current.x;
        const mouseY = e?.y ?? lastPosition.current.y;
        if (e) lastPosition.current = { x: mouseX, y: mouseY };

        const center = [left + width * 0.5, top + height * 0.5];
        const distanceFromCenter = Math.hypot(mouseX - center[0], mouseY - center[1]);
        const inactiveRadius = 0.5 * Math.min(width, height) * inactiveZone;

        if (distanceFromCenter < inactiveRadius) {
          element.style.setProperty("--active", "0");
          return;
        }

        const isActive =
          mouseX > left - proximity &&
          mouseX < left + width + proximity &&
          mouseY > top - proximity &&
          mouseY < top + height + proximity;

        element.style.setProperty("--active", isActive ? "1" : "0");
        if (!isActive) return;

        const currentAngle = parseFloat(element.style.getPropertyValue("--start")) || 0;
        let targetAngle =
          (180 * Math.atan2(mouseY - center[1], mouseX - center[0])) / Math.PI + 90;
        const angleDiff = ((targetAngle - currentAngle + 180) % 360) - 180;
        const newAngle = currentAngle + angleDiff;

        animate(currentAngle, newAngle, {
          duration: movementDuration,
          ease: [0.16, 1, 0.3, 1],
          onUpdate: (value) => element.style.setProperty("--start", String(value)),
        });
      });
    },
    [inactiveZone, proximity, movementDuration]
  );

  useEffect(() => {
    if (disabled) return;
    const handleScroll = () => handleMove();
    const handlePointerMove = (e) => handleMove(e);
    window.addEventListener("scroll", handleScroll, { passive: true });
    document.body.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      window.removeEventListener("scroll", handleScroll);
      document.body.removeEventListener("pointermove", handlePointerMove);
    };
  }, [handleMove, disabled]);

  if (disabled) return null;

  return (
    <div
      ref={containerRef}
      style={{
        "--blur": `${blur}px`,
        "--spread": spread,
        "--start": "0",
        "--active": "0",
        "--glowingeffect-border-width": `${borderWidth}px`,
        "--repeating-conic-gradient-times": "5",
        "--gradient": FINSIGHT_GRADIENT,
      }}
      className={cn(
        "glow-effect-layer",
        blur > 0 && "glow-blurred",
        className
      )}
    >
      <div className="glow" />
    </div>
  );
});

GlowingEffect.displayName = "GlowingEffect";
export { GlowingEffect };
