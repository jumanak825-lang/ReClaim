import { BrandLogo } from "@/components/brand-logo";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-12">
      <BrandLogo className="h-10" priority />
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
