import type { Metadata } from "next";
import { Barlow_Condensed, Geist, Geist_Mono } from "next/font/google";

import { metadata as siteMetadata } from "./metadata";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// The partners' broadcast graphics, inside the Broadcast Preview's monitor only.
const graphics = Barlow_Condensed({
  variable: "--font-graphics",
  subsets: ["latin", "latin-ext"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  // Only the Broadcast Preview uses it: no other route should wait on it.
  preload: false,
});

export const metadata: Metadata = siteMetadata;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${graphics.variable} h-full antialiased`}
    >
      <body>{children}</body>
    </html>
  );
}
