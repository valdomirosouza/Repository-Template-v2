import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "__SERVICE_NAME__",
  description: "TODO: describe this app",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
