// Cloudflare Worker shim — routes all traffic to the BEAT Django container.
// Secrets (DATABASE_URL, DJANGO_SECRET_KEY, ...) are Worker secrets forwarded
// into the container as environment variables. DYNO=web.1 makes settings.py
// take its Heroku production path (DEBUG off, wildcard ALLOWED_HOSTS).
import { Container, getContainer } from "@cloudflare/containers";

export class BeatContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "20m";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      DYNO: "web.1",
      // TLS terminates at the Cloudflare edge; an in-container redirect would
      // 301 the health-check ping to https:// and break container startup.
      DJANGO_SECURE_SSL_REDIRECT: "false",
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
    };
  }
}

export default {
  async fetch(request, env) {
    // Container port speaks plain HTTP; rewrite the scheme but keep
    // X-Forwarded-Proto=https (Cloudflare sets it) so Django's
    // SECURE_PROXY_SSL_HEADER still marks the request secure.
    const url = new URL(request.url);
    url.protocol = "http:";
    const proxied = new Request(url, request);
    // Django's SECURE_PROXY_SSL_HEADER needs this to treat requests as secure
    // (secure cookies, CSRF origin checks, https URL generation).
    proxied.headers.set("X-Forwarded-Proto", "https");
    return getContainer(env.BEAT_CONTAINER).fetch(proxied);
  },
};
