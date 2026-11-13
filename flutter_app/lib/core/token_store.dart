import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists the refresh token (the only thing that needs to survive an app
/// restart — the access token is short-lived and just kept in memory, same
/// split as the web app's in-memory access token + httpOnly refresh cookie).
///
/// The backend only ever hands out the refresh token via a `Set-Cookie` header
/// on /auth/login (see backend/app/auth/routes.py — `samesite="none"`,
/// `httponly=True`, path="/auth"). `httponly` only stops a browser's JS from
/// reading `document.cookie`; it does nothing to a raw HTTP client, so we parse
/// the header ourselves and resend it manually as a `Cookie` header — no
/// backend change needed to support a non-browser client.
class TokenStore {
  static const _refreshTokenKey = 'refresh_token';
  final _storage = const FlutterSecureStorage();

  Future<void> saveRefreshToken(String token) =>
      _storage.write(key: _refreshTokenKey, value: token);

  Future<String?> readRefreshToken() => _storage.read(key: _refreshTokenKey);

  Future<void> clearRefreshToken() => _storage.delete(key: _refreshTokenKey);

  /// Pulls `refresh_token=<value>` out of a raw `set-cookie` response header.
  /// Returns null if the header is absent or doesn't contain that cookie.
  static String? parseRefreshTokenFromSetCookie(String? setCookieHeader) {
    if (setCookieHeader == null) return null;
    final match = RegExp(r'refresh_token=([^;]+)').firstMatch(setCookieHeader);
    return match?.group(1);
  }
}
