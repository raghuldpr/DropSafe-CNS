// Cloudflare Pages Function: forwards /api/* to the backend so the browser sees one origin.
// This keeps auth cookies first-party and avoids CORS. Set BACKEND_URL in
// Pages > Settings > Environment variables, e.g. https://<user>-<space>.hf.space
export async function onRequest({ request, env }) {
  if (!env.BACKEND_URL) {
    return new Response('BACKEND_URL is not configured', { status: 500 });
  }
  const incoming = new URL(request.url);
  const target = new URL(incoming.pathname + incoming.search, env.BACKEND_URL);

  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.set('x-forwarded-host', incoming.host);
  headers.set('x-forwarded-proto', 'https');

  const hasBody = !['GET', 'HEAD'].includes(request.method);
  return fetch(target.toString(), {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    redirect: 'manual',
    duplex: 'half',
  });
}
