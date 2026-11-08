import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Reset password · Reclaim" };

// Password reset is out of scope for the hackathon demo (docs/11 §2); the API returns 501.
export default function ForgotPasswordPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h1>Reset your password</h1>
        </CardTitle>
        <CardDescription>Password reset isn&apos;t available in this demo.</CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        Use one of the demo accounts or create a new account.{" "}
        <Link href="/sign-in" className="font-medium text-primary underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      </CardContent>
    </Card>
  );
}
