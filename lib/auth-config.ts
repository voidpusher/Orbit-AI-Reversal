/**
 * Keep the login page and protected-route guard on the same auth mode.
 * Production defaults to authentication enabled; local development remains
 * frictionless unless NEXT_PUBLIC_AUTH_DISABLED is explicitly set to "false".
 */
export const AUTH_DISABLED =
  process.env.NEXT_PUBLIC_AUTH_DISABLED === "true" ||
  (process.env.NEXT_PUBLIC_AUTH_DISABLED === undefined && process.env.NODE_ENV !== "production");
