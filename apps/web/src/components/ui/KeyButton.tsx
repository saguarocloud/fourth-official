import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Intent = "primary" | "default" | "danger" | "quiet";

interface KeyButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  readonly children: ReactNode;
  readonly intent?: Intent;
  readonly size?: "sm" | "md";
  readonly loading?: boolean;
}

/** A square-cut hardware key, as on a vision mixer. The primary key is the lit one. */
export function KeyButton({
  children,
  intent = "default",
  size = "md",
  loading = false,
  disabled,
  type = "button",
  className,
  ...rest
}: KeyButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      data-intent={intent}
      data-size={size}
      className={["key", className].filter(Boolean).join(" ")}
    >
      {loading && <LoaderCircle aria-hidden="true" className="key__spinner" />}
      <span>{children}</span>
    </button>
  );
}
