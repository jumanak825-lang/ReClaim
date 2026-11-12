import Image from "next/image";
import Link from "next/link";
import logo from "@/public/brand/reclaim-logo.png";
import { cn } from "@/lib/utils";

/** The Reclaim logo, linking home. Drawn for light surfaces; size it with a height class. */
export function BrandLogo({ className, priority }: { className?: string; priority?: boolean }) {
  return (
    <Link href="/" className="inline-flex shrink-0 items-center rounded-md">
      <Image src={logo} alt="Reclaim" priority={priority} className={cn("h-8 w-auto", className)} />
    </Link>
  );
}
