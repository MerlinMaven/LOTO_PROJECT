import { clsx } from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-steel-700 text-white hover:bg-steel-800 focus:ring-steel-300",
  secondary:
    "bg-white text-steel-700 border border-steel-300 hover:bg-steel-50 focus:ring-steel-200",
  ghost: "bg-transparent text-steel-600 hover:bg-steel-100 focus:ring-steel-200",
  danger: "bg-hazard text-white hover:bg-red-800 focus:ring-red-300",
  success: "bg-approved text-white hover:bg-green-800 focus:ring-green-300",
};

const SIZES: Record<Size, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  leftIcon,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition",
        "outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && (
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {!loading && leftIcon}
      {children}
    </button>
  );
}
