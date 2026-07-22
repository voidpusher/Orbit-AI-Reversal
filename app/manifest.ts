import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Orbit Software Intelligence",
    short_name: "Orbit",
    description: "Evidence-backed software intelligence from observable product behavior.",
    start_url: "/",
    display: "standalone",
    background_color: "#050507",
    theme_color: "#07111a",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
