"use client";

import { useEffect } from "react";

export function OpticalGlassRuntime() {
  useEffect(() => {
    const root = document.documentElement;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (reducedMotion.matches) {
      root.style.setProperty("--glass-light-x", "50%");
      root.style.setProperty("--glass-light-y", "0%");
      return;
    }

    let targetX = 50;
    let targetY = 0;
    let currentX = targetX;
    let currentY = targetY;
    let frame = 0;

    const render = () => {
      currentX += (targetX - currentX) * 0.12;
      currentY += (targetY - currentY) * 0.12;
      root.style.setProperty("--glass-light-x", `${currentX.toFixed(2)}%`);
      root.style.setProperty("--glass-light-y", `${currentY.toFixed(2)}%`);

      if (Math.abs(targetX - currentX) > 0.04 || Math.abs(targetY - currentY) > 0.04) {
        frame = window.requestAnimationFrame(render);
      } else {
        frame = 0;
      }
    };

    const onPointerMove = (event: PointerEvent) => {
      targetX = (event.clientX / window.innerWidth) * 100;
      targetY = (event.clientY / window.innerHeight) * 100;
      if (!frame) frame = window.requestAnimationFrame(render);
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <svg className="optical-glass-defs" aria-hidden="true" focusable="false">
      <defs>
        <filter
          id="orbit-glass-refraction"
          x="-12%"
          y="-12%"
          width="124%"
          height="124%"
          colorInterpolationFilters="sRGB"
        >
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.008 0.028"
            numOctaves={2}
            seed={17}
            result="surfaceNoise"
          />
          <feGaussianBlur in="surfaceNoise" stdDeviation="0.65" result="softSurface" />
          <feDisplacementMap
            in="SourceGraphic"
            in2="softSurface"
            scale={7}
            xChannelSelector="R"
            yChannelSelector="B"
          />
        </filter>

        <filter
          id="orbit-glass-refraction-deep"
          x="-18%"
          y="-18%"
          width="136%"
          height="136%"
          colorInterpolationFilters="sRGB"
        >
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.006 0.021"
            numOctaves={2}
            seed={29}
            result="deepNoise"
          />
          <feGaussianBlur in="deepNoise" stdDeviation="0.9" result="deepSurface" />
          <feDisplacementMap
            in="SourceGraphic"
            in2="deepSurface"
            scale={13}
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
    </svg>
  );
}
