import { forwardRef } from "react";
import { ArrowRight } from "lucide-react";

/**
 * HoverButton — full interactive hover effect:
 *   • Default: text + optional icon visible, small teal dot rests at left
 *   • Hover: dot expands to fill button (teal), text slides right+fades,
 *            text + arrow slides in from the right on top of teal fill
 *
 * Props:
 *   text       — button label (required for slide effect)
 *   icon       — optional lucide icon component shown in default state
 *   variant    — "primary" | "ghost" (default: "primary")
 *   className  — extra CSS classes
 *   ...rest    — passed to <button>
 */
const HoverButton = forwardRef(function HoverButton(
  { text, children, className = "", variant = "primary", icon: Icon, disabled, ...props },
  ref
) {
  const label = text ?? (typeof children === "string" ? children : null);

  // No label → fall back to plain .btn button (icon-only etc.)
  if (!label) {
    return (
      <button
        ref={ref}
        className={`btn btn-${variant} ${className}`}
        disabled={disabled}
        {...props}
      >
        {Icon && <Icon size={15} />}
        {children}
      </button>
    );
  }

  return (
    <button
      ref={ref}
      className={`hvr-btn hvr-btn-${variant} ${className}`}
      disabled={disabled}
      {...props}
    >
      {/* Default text (slides right on hover) */}
      <span className="hvr-text">
        {Icon && <Icon size={15} />}
        {label}
      </span>

      {/* Overlay: text + arrow slides in from right on hover */}
      <span className="hvr-overlay">
        {label}
        <ArrowRight size={14} />
      </span>

      {/* Expanding dot */}
      <span className="hvr-dot" aria-hidden="true" />
    </button>
  );
});

export default HoverButton;
