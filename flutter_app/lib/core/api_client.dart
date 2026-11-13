import 'dart:convert';
import 'package:http/http.dart' as http;

import 'api_exception.dart';
import 'token_store.dart';

/// Same shape as frontend/lib/api.ts, adapted for a non-browser client:
///  - access token lives in memory only (cleared on app restart)
///  - refresh token is parsed out of Set-Cookie by hand (see TokenStore) and
///    resent as a Cookie header, since Dart's http client has no cookie jar
///  - a 401 on an `auth: true` call triggers one silent refresh-and-retry,
///    exactly like the web app's `tryRefresh()`
class ApiClient {
  final String baseUrl;
  final TokenStore tokenStore;
  final http.Client _client = http.Client();
  String? _accessToken;

  ApiClient({required this.baseUrl, required this.tokenStore});

  String? get accessToken => _accessToken;

  void setAccessToken(String? token) {
    _accessToken = token;
  }

  Future<dynamic> get(String path, {bool auth = false}) =>
      _request('GET', path, auth: auth);

  Future<dynamic> post(String path, {Object? body, bool auth = false}) =>
      _request('POST', path, body: body, auth: auth);

  Future<dynamic> patch(String path, {Object? body, bool auth = false}) =>
      _request('PATCH', path, body: body, auth: auth);

  Future<dynamic> delete(String path, {bool auth = false}) =>
      _request('DELETE', path, auth: auth);

  Future<dynamic> _request(
    String method,
    String path, {
    Object? body,
    bool auth = false,
    bool retry = true,
  }) async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (auth && _accessToken != null) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }

    final request = http.Request(method, Uri.parse('$baseUrl$path'));
    request.headers.addAll(headers);
    if (body != null) request.body = jsonEncode(body);

    final streamed = await _client.send(request);
    final res = await http.Response.fromStream(streamed);

    if (res.statusCode == 401 && auth && retry) {
      final refreshed = await tryRefresh();
      if (refreshed) {
        return _request(method, path, body: body, auth: auth, retry: false);
      }
    }

    if (res.statusCode >= 400) {
      throw ApiException(res.statusCode, _parseError(res));
    }

    if (res.statusCode == 204 || res.body.isEmpty) return null;
    return jsonDecode(res.body);
  }

  String _parseError(http.Response res) {
    try {
      final data = jsonDecode(res.body);
      if (data is Map && data['detail'] != null)
        return data['detail'].toString();
    } catch (_) {}
    return res.reasonPhrase ?? 'Something went wrong.';
  }

  /// Mirrors api.ts's tryRefresh(): POST /auth/refresh-token with whatever
  /// refresh-token cookie we have stored, and update the in-memory access token.
  Future<bool> tryRefresh() async {
    final refreshToken = await tokenStore.readRefreshToken();
    if (refreshToken == null) return false;

    try {
      final res = await _client.post(
        Uri.parse('$baseUrl/auth/refresh-token'),
        headers: {'Cookie': 'refresh_token=$refreshToken'},
      );
      if (res.statusCode != 200) return false;
      final data = jsonDecode(res.body);
      _accessToken = data['access_token'] as String;
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Login/signup need the raw response (to read Set-Cookie), so they bypass
  /// _request and call the underlying client directly.
  Future<http.Response> rawPost(String path, Object body) {
    return _client.post(
      Uri.parse('$baseUrl$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
  }
}
