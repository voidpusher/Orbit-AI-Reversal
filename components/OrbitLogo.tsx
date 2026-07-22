type OrbitLogoProps = {
  className?: string;
};

export function OrbitLogo({ className = "" }: OrbitLogoProps) {
  return (
    <span className={`brand-mark${className ? ` ${className}` : ""}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" role="presentation">
        <circle className="orbit-logo-ring" cx="16" cy="16" r="9.5" />
        <circle className="orbit-logo-dot" cx="23.25" cy="9.85" r="2.15" />
      </svg>
    </span>
  );
}
