import type { Metadata } from "next";
import { Suspense } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SignInForm } from "@/components/auth/sign-in-form";

export const metadata: Metadata = { title: "Sign in · Reclaim" };

export default function SignInPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h1>Sign in</h1>
        </CardTitle>
        <CardDescription>Owners, finders and organisation staff all sign in here.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense>
          <SignInForm />
        </Suspense>
      </CardContent>
    </Card>
  );
}
