"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const [checked, setChecked] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    // Don't check on onboarding page itself
    if (pathname === "/onboarding") {
      setChecked(true);
      return;
    }

    api.onboardingStatus()
      .then((res) => {
        if (!res.completed) {
          router.replace("/onboarding");
        } else {
          setChecked(true);
        }
      })
      .catch(() => {
        // If we can't check (network error etc.), just proceed
        setChecked(true);
      });
  }, [pathname, router]);

  if (!checked && pathname !== "/onboarding") return null;
  return <>{children}</>;
}
