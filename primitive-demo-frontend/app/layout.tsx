import './globals.css';
import Link from 'next/link';

export const metadata = {
  title: 'PrimitiveOS Demo',
  description: 'Primitive-as-a-Service product demo'
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <div className="brand">PrimitiveOS</div>

          <div className="links">
            <Link href="/tools">Tools</Link>
            <Link href="/chat">Chat</Link>
            <Link href="/mas">MAS</Link>
            <Link href="/booking">Booking</Link>
          </div>
        </nav>

        {children}
      </body>
    </html>
  );
}