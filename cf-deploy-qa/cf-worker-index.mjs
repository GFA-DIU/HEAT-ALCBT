// Cloudflare Worker shim — BEAT QA backend container (qa branch, API module).
import { Container, getContainer } from "@cloudflare/containers";

export class BeatQaContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "20m";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      DYNO: "web.1",
      DJANGO_SECURE_SSL_REDIRECT: "false",
      // qa branch reads SUPABASE_DATABASE_URL (settings.py dj_database_url env)
      SUPABASE_DATABASE_URL: env.DATABASE_URL,
      DATABASE_URL: env.DATABASE_URL,
      DJANGO_SECRET_KEY: env.DJANGO_SECRET_KEY,
      FIELD_ENCRYPTION_KEY: env.FIELD_ENCRYPTION_KEY,
      EMAIL_HOST_USER: env.EMAIL_HOST_USER ?? "",
      EMAIL_HOST_PASSWORD: env.EMAIL_HOST_PASSWORD ?? "",
      DEFAULT_FROM_EMAIL: env.DEFAULT_FROM_EMAIL ?? "",
      HONEYBADGER_API_KEY: env.HONEYBADGER_API_KEY ?? "",
      DJANGO_ADMIN_URL: env.DJANGO_ADMIN_URL ?? "",
      ECO_PLATFORM_TOKEN: env.ECO_PLATFORM_TOKEN ?? "",
      NOMINATIM_AGENT_STRING: env.NOMINATIM_AGENT_STRING ?? "",
      REPORT_API_KEY: env.REPORT_API_KEY ?? "",
      SITE_DOMAIN: env.SITE_DOMAIN ?? "",
      SITE_NAME: env.SITE_NAME ?? "",
    };
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    url.protocol = "http:";
    const proxied = new Request(url, request);
    proxied.headers.set("X-Forwarded-Proto", "https");
    return getContainer(env.BEAT_QA_CONTAINER).fetch(proxied);
  },
};
