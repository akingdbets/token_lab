## Concepts and setup
- **JWT** is a compact, signed—not encrypted—string: anyone can read its payload, but the signature lets the server verify it issued the token and it was not modified. It can include an expiry.
- Store one-way password hashes, never passwords. Install with `uv add pyjwt` and `uv add "pwdlib[argon2]"`. `pwdlib` recommends Argon2 and also supports bcrypt; for legacy hashes (e.g. Django), consider `passlib` to verify old hashes while hashing new ones with Argon2/bcrypt. For RSA/ECDSA, install `pyjwt[crypto]`.

## The full example and walkthrough
- `docs_src/security/tutorial004_an_py310.py` uses `PasswordHash.recommended()`, `password_hash.hash(password)` and `password_hash.verify(plain, hashed)`. `fake_users_db` stores `johndoe` with an Argon2 hash of `secret`; plaintext `secret` never appears in code or the database.
- `authenticate_user` verifies against `DUMMY_HASH` when a user does not exist, avoiding faster rejection of unknown usernames that could enable timing-based enumeration.
- `SECRET_KEY` is shown as `"09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"`; generate it with `openssl rand -hex 32` and keep it out of source control (e.g. load it via Settings). `ALGORITHM = "HS256"` (HMAC with SHA-256). `ACCESS_TOKEN_EXPIRE_MINUTES = 30`.
- `create_access_token` adds an `exp` claim in UTC; if no `expires_delta` is given, it uses 15 minutes. PyJWT rejects expired tokens on decode with an `InvalidTokenError` subclass.
- Login at `POST /token` uses `OAuth2PasswordRequestForm` and returns `Token(access_token=..., token_type="bearer")`, the OAuth2-required response shape. It puts the username in `sub`. `sub` should be a string unique across the whole application; prefix it (e.g. `"username:johndoe"`) if tokens may identify different kinds of entities.
- `get_current_user` decodes via `jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])` (always pin accepted algorithms), reads `sub`, and loads the user. Bad signature, expired token, missing `sub`, or unknown user all produce `401`, detail `"Could not validate credentials"`, and `WWW-Authenticate: Bearer`. `get_current_active_user` rejects disabled users with `400`, `"Inactive user"`.
- `/users/me/` returns the active user. In `/docs`, click **Authorize**, log in with `johndoe` / `secret`, then call `/users/me/`; the client sends `Authorization: Bearer <JWT>`. JWT payloads are readable but signed.

## Next steps and related
- Replace `fake_users_db` with real storage, e.g. SQL Databases; add permissions with OAuth2 Scopes. FastAPI does not require particular libraries; `PyJWT` and `pwdlib` are well-maintained choices used via ordinary dependencies.
- Related: Security Basics: OAuth2 Password Flow and Current User; HTTP Basic, Bearer, API Keys.
