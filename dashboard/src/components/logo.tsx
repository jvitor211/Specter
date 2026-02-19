export function SpecterLogo({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dims = { sm: 28, md: 36, lg: 48 }[size];
  const dotR = { sm: 4, md: 5, lg: 7 }[size];
  const ringR = { sm: 8, md: 10, lg: 14 }[size];

  return (
    <svg
      width={dims}
      height={dims}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="flex-shrink-0"
    >
      <rect width="36" height="36" rx="8" fill="rgba(255,45,74,0.1)" />
      <circle cx="18" cy="18" r={dotR} fill="#ff2d4a">
        <animate
          attributeName="opacity"
          values="1;0.5;1"
          dur="2.5s"
          repeatCount="indefinite"
        />
      </circle>
      <circle
        cx="18"
        cy="18"
        r={ringR}
        stroke="#ff2d4a"
        strokeOpacity="0.3"
        strokeWidth="1"
        fill="none"
      />
    </svg>
  );
}

export function SpecterWordmark() {
  return (
    <span className="font-titulo font-extrabold text-lg tracking-tight text-texto-primario">
      SPECTER
    </span>
  );
}
