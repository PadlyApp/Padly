import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Padly",
  description: "Your collaborative workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

