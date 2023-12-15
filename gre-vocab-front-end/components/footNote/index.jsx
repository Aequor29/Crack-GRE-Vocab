import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-content1-200 text-center text-xs p-3 relative bottom-0 w-full border-t">
      <div>
        © {new Date().getFullYear()} Developed by Richard Hu. All rights
        reserved.
      </div>
      <div>
        Contact me at:{" "}
        <a href="mailto:info@crackgrevocab.com">rihu2024@outlook.com</a>
      </div>
      <div>
        <Link href="/About">About The Project</Link>
      </div>
    </footer>
  );
}
