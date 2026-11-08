"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { fieldErrors } from "@/lib/api/form-errors";
import { homeFor, meQueryKey } from "@/lib/api/me";
import { safeNext } from "@/lib/safe-next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "./field";

export function SignInForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const queryClient = useQueryClient();

  const signIn = useMutation({
    mutationFn: (body: { email: string; password: string }) => unwrap(api.POST("/api/v1/auth/login", { body })),
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
      router.replace(next ?? homeFor(me));
    },
  });

  const errors = fieldErrors(signIn.error);
  const formError =
    signIn.error instanceof ApiError && signIn.error.code === "INVALID_CREDENTIALS"
      ? "Email or password is incorrect."
      : signIn.error && !Object.keys(errors).length
        ? "We couldn't sign you in. Try again."
        : null;

  return (
    <form
      noValidate
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        signIn.mutate({ email: String(data.get("email")), password: String(data.get("password")) });
      }}
    >
      {formError && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}
      <Field id="email" label="Email" type="email" autoComplete="email" required error={errors.email} />
      <Field
        id="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        required
        error={errors.password}
      />
      <Button type="submit" disabled={signIn.isPending}>
        {signIn.isPending ? "Signing in…" : "Sign in"}
      </Button>
      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="text-muted-foreground underline-offset-4 hover:underline">
          Forgot password?
        </Link>
        <Link
          href={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Create an account
        </Link>
      </div>
    </form>
  );
}
