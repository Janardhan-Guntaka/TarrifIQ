import Link from "next/link";
import { APP_NAME } from "@/lib/constants";

type Props = {
  showCta?: boolean;
};

export function SiteHeader({ showCta = true }: Props) {
  return (
    <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white">
            TQ
          </span>
          <span className="text-lg font-semibold tracking-tight text-slate-900">{APP_NAME}</span>
        </Link>
        {showCta && (
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="hidden text-sm font-medium text-slate-600 hover:text-slate-900 sm:inline"
            >
              Sign in
            </Link>
            <Link
              href="/login"
              className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-dark"
            >
              Get started
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
