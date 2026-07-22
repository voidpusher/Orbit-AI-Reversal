export function OpticalGlassRuntime() {
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
