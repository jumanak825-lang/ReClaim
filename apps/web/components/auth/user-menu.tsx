"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut } from "lucide-react";
import { api, unwrapRaw } from "@/lib/api/client";
import { useMe } from "@/lib/api/me";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function UserMenu() {
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const router = useRouter();
  const signOut = useMutation({
    mutationFn: () => unwrapRaw(api.POST("/api/v1/auth/logout")),
    // Sign out locally even if the server call fails, so the user isn't stuck.
    onSettled: () => {
      queryClient.clear();
      router.replace("/sign-in");
    },
  });

  if (!me) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="max-w-48">
          <span className="truncate">{me.display_name}</span>
          <ChevronDown className="size-4" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate font-medium">{me.display_name}</span>
          <span className="block truncate text-muted-foreground">{me.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/dashboard">My dashboard</Link>
        </DropdownMenuItem>
        {me.memberships.map((m) => (
          <DropdownMenuItem key={m.organisation_id} asChild>
            <Link href={`/org/${m.organisation_slug}`}>{m.organisation_name}</Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => signOut.mutate()} disabled={signOut.isPending}>
          <LogOut className="size-4" aria-hidden />
          {signOut.isPending ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
