"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NavSignInButton = () => {
  const pathname = usePathname();
  const returnTo =
    pathname && pathname !== "/login" ? `?returnTo=${encodeURIComponent(pathname)}` : "";

  return (
    <Link href={`/login${returnTo}`} className="nav-signin-btn">
      Sign in
    </Link>
  );
};
