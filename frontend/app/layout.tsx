import "./globals.css";

export const metadata = {
  title: "OmniMind AI",
  description: "One AI that can do almost everything.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
