/**
 * Thin wrappers over navigator.credentials for the L2 flow. The server owns all policy; this file
 * only converts between the browser's ArrayBuffer world and the base64url JSON the API speaks.
 *
 *   enroll(fetch, sessionPath)          -> credential view       (Touch ID once)
 *   signHead(fetch, sessionPath, head) -> AttestResponse        (silent or Touch ID, per `uv`)
 */

export const webauthnAvailable = () =>
  typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials

export const b64url = {
  encode: (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''),
  decode: (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(s.length / 4) * 4, '=')), (c) => c.charCodeAt(0)),
}

const hexToBytes = (hex) => Uint8Array.from(hex.match(/../g), (h) => parseInt(h, 16))

async function json(r) {
  const body = await r.json().catch(() => ({}))
  if (!r.ok) {
    const err = new Error(typeof body.detail === 'string' ? body.detail : body.detail?.detail || `HTTP ${r.status}`)
    err.status = r.status
    err.detail = body.detail
    throw err
  }
  return body
}

/** Create a platform-authenticator key for this session's owner and register its public half. */
export async function enroll(fetchFn, sessionPath, label = null) {
  if (!webauthnAvailable()) throw new Error('This browser has no WebAuthn support')
  const opts = await json(await fetchFn(`${sessionPath}/enroll/options`))
  const cred = await navigator.credentials.create({
    publicKey: {
      ...opts,
      challenge: b64url.decode(opts.challenge),
      user: { ...opts.user, id: b64url.decode(opts.user.id) },
      excludeCredentials: (opts.excludeCredentials || []).map((c) => ({ ...c, id: b64url.decode(c.id) })),
    },
  })
  return json(await fetchFn(`${sessionPath}/enroll`, {
    method: 'POST',
    body: JSON.stringify({
      id: cred.id,
      attestation_object: b64url.encode(cred.response.attestationObject),
      client_data_json: b64url.encode(cred.response.clientDataJSON),
      transports: cred.response.getTransports?.() ?? [],
      label,
    }),
  }))
}

/**
 * Sign a chain head with an enrolled key. `uv: 'required'` forces Touch ID / PIN (the seal);
 * `'discouraged'` lets the authenticator sign silently when it can (mid-session checkpoints).
 */
export async function signHead(fetchFn, sessionPath, headHex, credentialIds, uv = 'discouraged') {
  if (!webauthnAvailable()) throw new Error('This browser has no WebAuthn support')
  const rpId = new URL(window.location.href).hostname
  const assertion = await navigator.credentials.get({
    publicKey: {
      challenge: hexToBytes(headHex),
      rpId,
      allowCredentials: credentialIds.map((id) => ({ type: 'public-key', id: b64url.decode(id) })),
      userVerification: uv,
      timeout: 60_000,
    },
  })
  return json(await fetchFn(`${sessionPath}/attest`, {
    method: 'POST',
    body: JSON.stringify({
      head: headHex,
      credential_id: assertion.id,
      authenticator_data: b64url.encode(assertion.response.authenticatorData),
      client_data_json: b64url.encode(assertion.response.clientDataJSON),
      signature: b64url.encode(assertion.response.signature),
    }),
  }))
}

export async function listCredentials(fetchFn, sessionPath) {
  return json(await fetchFn(`${sessionPath}/credentials`))
}
