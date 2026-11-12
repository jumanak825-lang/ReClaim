"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, rateLimitMessage, unwrap } from "@/lib/api/client";
import { fieldErrors } from "@/lib/api/form-errors";
import { homeFor, meQueryKey } from "@/lib/api/me";
import { safeNext } from "@/lib/safe-next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "./field";

type Body = { display_name: string; email: string; password: string };

export function RegisterForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const queryClient = useQueryClient();

  const register = useMutation({
    mutationFn: (body: Body) => unwrap(api.POST("/api/v1/auth/register", { body })),
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
      router.replace(next ?? homeFor(me));
    },
  });

  const errors = fieldErrors(register.error);
  // The server's message is deliberately generic so it doesn't reveal whether an email is registered.
  const formError =
    rateLimitMessage(register.error) ??
    (register.error instanceof ApiError && register.error.code === "REGISTRATION_FAILED"
      ? "We couldn't create an account with these details. If you already have one, sign in instead."
      : register.error && !Object.keys(errors).length
        ? "We couldn't create your account. Try again."
        : null);

  return (
    <form
      noValidate
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        register.mutate({
          display_name: String(data.get("display_name")).trim(),
          email: String(data.get("email")).trim(),
          password: String(data.get("password")),
        });
      }}
    >
      {formError && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}
      <Field id="display_name" label="Your name" autoComplete="name" required maxLength={80} error={errors.display_name} />
      <Field id="email" label="Email" type="email" autoComplete="email" required error={errors.email} />
      <Field
        id="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        maxLength={128}
        hint="At least 8 characters."
        error={errors.password}
      />
      <Button type="submit" disabled={register.isPending}>
        {register.isPending ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href={next ? `/sign-in?next=${encodeURIComponent(next)}` : "/sign-in"}
          className="font-medium text-brand underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}
