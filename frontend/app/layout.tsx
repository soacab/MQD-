import type { Metadata } from "next";
import { AppNav } from "./AppNav";
import "./styles.css";

export const metadata: Metadata = {
  title: "CheckFlow",
  description: "MQD inspection workflow"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <AppNav />
          {children}
        </div>
      </body>
    </html>
  );
}
