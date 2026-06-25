import { PRODUCT_DISCLAIMER } from "@/lib/constants";

type Props = {
  variant?: "banner" | "footer";
};

export function Disclaimer({ variant = "banner" }: Props) {
  if (variant === "footer") {
    return (
      <p className="text-xs leading-relaxed text-slate-500">{PRODUCT_DISCLAIMER}</p>
    );
  }
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-950">
      <span className="font-medium">Early access — </span>
      {PRODUCT_DISCLAIMER}
    </div>
  );
}
