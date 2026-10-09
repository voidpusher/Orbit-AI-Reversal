type OrbitLogoProps = {
  className?: string;
};

export function OrbitLogo({ className = "" }: OrbitLogoProps) {
  return (
    <span className={`brand-mark${className ? ` ${className}` : ""}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" role="presentation" fill="none">
        <path className="orbit-logo-path" d="M20 6H13a7 7 0 0 0-7 7v6a7 7 0 0 0 7 7h6a7 7 0 0 0 7-7v-7" />
        <path className="orbit-logo-path" d="M22 6h4v4M17 15l9-9" />
      </svg>
    </span>
  );
}
