import { OrbitLogo } from "@/components/OrbitLogo";

export default function Loading() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <OrbitLogo className="route-loading-mark" />
      <span>Loading Orbit…</span>
    </div>
  );
}
