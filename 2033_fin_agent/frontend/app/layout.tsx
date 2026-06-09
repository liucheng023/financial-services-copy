import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "FinAgentOS",
  description: "Financial Expert Agent Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-zinc-100`}
      >
        <div className="flex h-screen">
          <aside className="w-64 border-r border-zinc-800 p-4 flex flex-col">
            <h1 className="text-lg font-bold mb-6 text-zinc-100">FinAgentOS</h1>
            <nav className="flex flex-col gap-1 flex-1">
              <a
                href="/agents"
                className="px-3 py-2 rounded-md text-sm hover:bg-zinc-800 text-zinc-300 hover:text-zinc-100"
              >
                Experts
              </a>
            </nav>
          </aside>
          <main className="flex-1 overflow-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
