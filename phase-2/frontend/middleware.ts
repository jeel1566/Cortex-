import { NextResponse } from "next/server";

// We check if Clerk keys are configured. If they are missing, we fall back
// to a mock/pass-through developer mode to prevent server crashes before Clerk is set up.
const hasClerkKeys = 
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && 
  process.env.CLERK_SECRET_KEY;

let clerkMiddleware: any;

try {
  if (hasClerkKeys) {
    const { authMiddleware } = require("@clerk/nextjs");
    clerkMiddleware = authMiddleware({
      publicRoutes: ["/", "/login", "/api/public"]
    });
  } else {
    clerkMiddleware = () => {
      return NextResponse.next();
    };
  }
} catch (e) {
  // If Clerk package is not fully loaded, fallback to pass-through
  clerkMiddleware = () => {
    return NextResponse.next();
  };
}

export default clerkMiddleware;

export const config = {
  matcher: ["/((?!.+\\.[\\w]+$|_next).*)", "/", "/(api|trpc)(.*)", "/__clerk/:path*"],
};
