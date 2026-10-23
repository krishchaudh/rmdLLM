import Link from "next/link";
import { AccountMenu } from "./AccountMenu";

export function Header({ right, left }: { right?: React.ReactNode; left?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[var(--bg)]/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
        {left}
        <Link href="/" className="group flex items-baseline gap-2">
          <span className="font-serif text-xl tracking-tight">RMD</span>
          <span className="hidden text-sm text-stone-500 sm:inline">Knowledge Assistant</span>
        </Link>
        <nav className="flex items-center gap-5 text-sm text-stone-500">
          <Link href="/sources" className="hover:text-stone-900">
            Sources
          </Link>
          <Link href="/admin" className="hover:text-stone-900">
            Admin
          </Link>
          {right ?? <AccountMenu />}
        </nav>
      </div>
    </header>
  );
}
