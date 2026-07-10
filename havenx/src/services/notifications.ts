import { db } from "@/lib/db";
import type { NotificationService } from "./types";

/**
 * In-app notifications are written to the database (real in every mode).
 * Email delivery is mocked to the console unless RESEND_API_KEY is set,
 * in which case it sends through Resend's HTTP API.
 */
export class DefaultNotificationService implements NotificationService {
  async notify(input: {
    userId: string;
    email: string;
    type: string;
    title: string;
    body: string;
    href?: string;
  }) {
    await db.notification.create({
      data: {
        userId: input.userId,
        type: input.type,
        title: input.title,
        body: input.body,
        href: input.href,
      },
    });
    await this.sendEmail(input.email, input.title, input.body, input.href);
  }

  async sendMagicLink(email: string, url: string) {
    await this.sendEmail(
      email,
      "Sign in to HavenX",
      `Click to sign in to your HavenX dashboard: ${url}`,
      url
    );
  }

  private async sendEmail(
    to: string,
    subject: string,
    body: string,
    href?: string
  ) {
    const apiKey = process.env.RESEND_API_KEY;
    if (!apiKey) {
      console.log(
        `[email:mock] to=${to} subject="${subject}" body="${body}"${href ? ` link=${href}` : ""}`
      );
      return;
    }
    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: process.env.EMAIL_FROM ?? "HavenX <onboarding@resend.dev>",
        to,
        subject,
        html: `<p>${body}</p>${href ? `<p><a href="${href}">Open</a></p>` : ""}`,
      }),
    });
  }
}
