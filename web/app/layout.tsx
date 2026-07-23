import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TeacherOS — Lesson Generation",
  description:
    "A teacher-friendly workspace for browsing curriculum and generating complete TeacherOS lesson packages.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
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
