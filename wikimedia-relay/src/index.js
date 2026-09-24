// curiosity-radar dev-only Wikimedia/Wikidata relay.
//
// Purpose: this repo's Claude Code cloud sessions cannot reach
// wikimedia.org/wikidata.org/wikipedia.org directly (egress block — see
// SPEC.md §9 item 8). This Worker runs somewhere that *can* reach them and
// relays a narrowly allow-listed set of read-only GET requests through, so
// dev sessions can (re)build tests/cassettes/ and evals/cassettes/ fixtures
// for new topics/languages without a manual "run this on your own machine
// and paste it back" handoff.
//
// It is NOT part of the shipped curiosity-radar skill and the skill's own
// runtime code never calls it — see wikimedia-relay/README.md.

const ALLOWED_HOSTS = [
  "wikimedia.org", // AQS pageviews REST API
  "www.wikidata.org", // Wikidata action API
];
const WIKIPEDIA_HOST_RE = /^[a-z-]+\.wikipedia\.org$/;

const UPSTREAM_USER_AGENT =
  "curiosity-radar-relay/0.1 (https://github.com/binskea/topic-scout; contact: marina@binskea.com; dev-tool, not the shipped skill)";

function isAllowedHost(hostname) {
  return ALLOWED_HOSTS.includes(hostname) || WIKIPEDIA_HOST_RE.test(hostname);
}

function jsonError(status, code, message) {
  return new Response(JSON.stringify({ error: { code, message } }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET") {
      return jsonError(405, "method_not_allowed", "Only GET is relayed.");
    }

    const token = request.headers.get("x-relay-token") || "";
    if (!env.RELAY_TOKEN || token !== env.RELAY_TOKEN) {
      return jsonError(401, "unauthorized", "Missing or invalid X-Relay-Token.");
    }

    const requestUrl = new URL(request.url);
    if (requestUrl.pathname !== "/relay") {
      return jsonError(404, "not_found", "Use GET /relay?url=<encoded target url>.");
    }

    const target = requestUrl.searchParams.get("url");
    if (!target) {
      return jsonError(400, "missing_url", "Query param 'url' is required.");
    }

    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch {
      return jsonError(400, "invalid_url", "Query param 'url' is not a valid URL.");
    }

    if (targetUrl.protocol !== "https:") {
      return jsonError(400, "invalid_scheme", "Only https:// targets are relayed.");
    }
    if (!isAllowedHost(targetUrl.hostname)) {
      return jsonError(
        403,
        "host_not_allowed",
        `Host '${targetUrl.hostname}' is not on the allow-list (wikimedia.org, www.wikidata.org, *.wikipedia.org).`
      );
    }

    let upstream;
    try {
      upstream = await fetch(targetUrl.toString(), {
        method: "GET",
        headers: { "user-agent": UPSTREAM_USER_AGENT, accept: "application/json" },
      });
    } catch (err) {
      return jsonError(502, "upstream_unreachable", String(err));
    }

    const body = await upstream.arrayBuffer();
    const headers = new Headers();
    const contentType = upstream.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    headers.set("x-relay-upstream-status", String(upstream.status));

    return new Response(body, { status: upstream.status, headers });
  },
};
