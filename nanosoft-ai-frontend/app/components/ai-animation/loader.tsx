"use client";

import type { SVGProps } from "react";

interface LoaderProps extends SVGProps<SVGSVGElement> {
  variant?: "classic";
  size?: number | string;
}

export function Loader({ variant = "classic", size = 18, className, style, ...props }: LoaderProps) {
  if (variant !== "classic") return null;

  return (
    <svg
      {...props}
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="status"
      aria-label="Loading"
      style={{ color: "currentColor", ...style }}
    >
      <style>{`@keyframes classic-loader-fade{0%,100%{opacity:.2}50%{opacity:1}}`}</style>
      {Array.from({ length: 12 }, (_, index) => {
        const angle = index * 30;
        return (
          <line
            key={angle}
            x1="12"
            y1="2.5"
            x2="12"
            y2="6.5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            transform={`rotate(${angle} 12 12)`}
            style={{ animation: "classic-loader-fade 1.2s ease-in-out infinite", animationDelay: `${index * 0.1}s` }}
          />
        );
      })}
    </svg>
  );
}
