import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

export async function passwordResetLink(email: string): Promise<string> {
  const directory = process.env.E2E_MAIL_DIR;
  if (!directory) {
    throw new Error("The isolated mail directory was not configured by the runner.");
  }
  for (const filename of await readdir(directory)) {
    const message = await readFile(join(directory, filename), "utf8");
    const recipient = message.indexOf(`To: ${email}`);
    if (recipient !== -1) {
      const link = message
        .slice(recipient)
        .match(/http:\/\/127\.0\.0\.1:\d+\/reset-password\/confirm\?[^\s]+/)?.[0];
      if (link && new URL(link).origin === process.env.E2E_BASE_URL) {
        return link;
      }
    }
  }
  throw new Error(`No local password-reset email found for ${email}.`);
}
