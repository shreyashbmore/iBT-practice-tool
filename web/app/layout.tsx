import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "iBT Practice",
  description: "Practice and estimated scoring for the 2026 TOEFL iBT format",
};

const nav = [
  { href: "/", label: "Home" },
  { href: "/progress", label: "Progress" },
  { href: "/history", label: "History" },
  { href: "/mic-check", label: "Mic check" },
  { href: "/review", label: "Content" },
  { href: "/rate", label: "Rate" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <nav className="mx-auto flex max-w-4xl items-center gap-6 px-6 py-3">
            <Link href="/" className="font-semibold text-indigo-700">iBT Practice</Link>
            {nav.slice(1).map((n) => (
              <Link key={n.href} href={n.href} className="text-sm text-slate-600 hover:text-slate-900">
                {n.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-4xl px-6 pb-8 text-xs text-slate-500">
          Not affiliated with or endorsed by ETS. TOEFL is a registered trademark of ETS. All scores are estimates.
        </footer>
      </body>
    </html>
  );
}
