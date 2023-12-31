import { Providers } from "./providers";
import { Inter } from "next/font/google";
import "./globals.css";
import Nav from "@/components/navigation/Navbar";
import { AuthProvider } from "./AuthContext";
import Footer from "@/components/footNote";

export const metadata = {
  title: "Crack GRE Vocabulary",
  description: "The best way to learn GRE vocabulary",
};

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        className={`${inter.className} prose prose-neutral dark:prose-invert w-full max-w-full`}
      >
        <Providers>
          <AuthProvider>
            <div className="flex flex-col min-h-screen">
              <Nav />
              {children}
              <Footer />
            </div>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
