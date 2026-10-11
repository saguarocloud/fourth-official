import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

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

export const metadata: Metadata = siteMetadata;

// Design direction contract, emitted as the first child of <body> so it survives the build.
const DIRECTION_CONTRACT = `<!--
THESIS: The control room speaks the fourth official's language: the LED board. Lit dot-matrix
numerals on a black panel field; state is the board's red, green and amber light. Refuses the
generic dark SaaS dashboard of rounded cards and glowing charts.
OWN-WORLD: Anodised near-black panels joined by hairlines; square-cut hardware keys; round status
lamps; 5x7 dot-matrix readouts with faint unlit dots; Geist for UI text with tabular figures.
Colour appears only as signal light: green verified, red on air or out, amber pending, violet
amended, blue AI.
STORY: An executive sees in five seconds that every match is under control and nothing wrong is
on air; an operator scans lamps, tallies and counts, then drills in.
FIRST VIEWPORT: Status bar (product, studio, replay label, p95 vs SLO, approvals, corrections,
cost, LED studio clock); screen rail left; featured match board across the top of the wall, two
boards below; live rail right with the latest correction as OUT/IN board above the activity log.
FORM: Fourth official's LED substitution board, candidate 7 of 7; seed key 7a5e2868.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
-->`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body>
        <div hidden dangerouslySetInnerHTML={{ __html: DIRECTION_CONTRACT }} />
        {children}
      </body>
    </html>
  );
}
