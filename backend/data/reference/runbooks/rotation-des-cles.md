# Rotating an exposed key

Owner: Data team. Trigger: a key was read, used or published outside its intended use.

1. Revoke the exposed key immediately in the secrets manager or the provider's console.
2. Issue a new key limited to the intended use, read-only if possible, with a short lifetime.
3. Update the services that used the old key, then check that they work.
4. Remove the secret from every file of the repository and of the agents' workspace, .env files included.
5. Review the old key's usage logs to spot any abnormal use since it was exposed.
6. Record the incident, the revocation date and the new key's name in the secrets register.
