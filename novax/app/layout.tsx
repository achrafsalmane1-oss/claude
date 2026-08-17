import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'novaX',
  description: 'Newly registered domain signal engine',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
