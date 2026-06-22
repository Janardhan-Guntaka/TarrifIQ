import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TariffIQ — US Import Duty Calculator",
  description: "AI-powered HTS classification and duty estimation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
